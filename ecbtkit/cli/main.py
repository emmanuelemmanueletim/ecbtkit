"""eCBTKit CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(name="ecbt", help="eCBTKit — Build CBT APIs, not CBT engines.", add_completion=False)
console = Console()


@app.command()
def version():
    from ecbtkit import __version__, __author__
    console.print(f"[bold green]eCBTKit[/] v{__version__}")
    console.print(f"Author: {__author__}")


@app.command()
def create(name: str = typer.Argument(...), path: Optional[Path] = typer.Option(None)):
    target = path or Path.cwd() / name
    if target.exists():
        console.print(f"[red]Exists: {target}[/]")
        raise typer.Exit(1)
    target.mkdir(parents=True)
    (target / "main.py").write_text(
        '''from ecbtkit import CBT

app = CBT()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
'''
    )
    (target / ".env").write_text(
        f"ECBT_APP_NAME={name}\n"
        "ECBT_DEBUG=true\n"
        "ECBT_DATABASE_URL=sqlite:///./ecbtkit.db\n"
        "ECBT_DATABASE_AUTO_CREATE=true\n"
        "ECBT_SECRET_KEY=change-me-to-a-long-random-string-please-32chars\n"
        "ECBT_CORS_ORIGINS=http://127.0.0.1:3000\n"
    )
    console.print(Panel.fit(
        f"[green]Created[/] {target}\n\n  cd {name}\n  pip install -e /path/to/ecbtkit\n  ecbt migrate\n  python main.py",
        title="eCBTKit",
    ))


@app.command()
def dev(host: str = "127.0.0.1", port: int = 8000):
    """Start with auto-create tables (local development only)."""
    import os
    os.environ.setdefault("ECBT_DATABASE_AUTO_CREATE", "true")
    from ecbtkit.core.config import get_settings
    get_settings.cache_clear()
    from ecbtkit import CBT
    console.print(f"[green]Starting[/] http://{host}:{port}/docs")
    CBT(create_tables=True).run(host=host, port=port)


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
    full_name: str = typer.Option("Administrator", prompt=True),
):
    from ecbtkit.db.base import init_db, session_scope, tables_exist, create_all_tables
    from ecbtkit.models.user import User, UserRole
    from ecbtkit.security.passwords import hash_password, validate_password_strength
    from ecbtkit.core.config import get_settings

    validate_password_strength(password)
    init_db()
    if not tables_exist():
        if get_settings().database_auto_create:
            create_all_tables()
        else:
            console.print("[red]Database not migrated. Run: ecbt migrate[/]")
            raise typer.Exit(1)
    with session_scope() as db:
        if db.query(User).filter(User.email == email.lower()).first():
            console.print("[red]Email already registered[/]")
            raise typer.Exit(1)
        db.add(User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.ADMINISTRATOR,
            is_active=True,
            is_verified=True,
        ))
        console.print(f"[green]Administrator created:[/] {email}")


@app.command()
def migrate():
    """Apply Alembic migrations (alembic upgrade head)."""
    try:
        import alembic  # noqa: F401
    except ImportError:
        console.print(
            "[red]Alembic is required for migrations.[/]\n"
            "Install: [cyan]pip install alembic[/] or [cyan]pip install ecbtkit[alembic][/]"
        )
        raise typer.Exit(1)
    try:
        from ecbtkit.db.base import run_alembic_upgrade
        run_alembic_upgrade("head")
        console.print("[green]Migrations applied (alembic upgrade head)[/]")
    except Exception as exc:
        console.print(f"[red]Migration failed:[/] {exc}")
        raise typer.Exit(1)


@app.command("check-production")
def check_production():
    """Validate production settings."""
    from ecbtkit.ops.production import validate_production_settings
    from ecbtkit.core.config import get_settings
    problems = validate_production_settings(get_settings())
    if not problems:
        console.print("[green]Production configuration looks safe[/]")
    else:
        for p in problems:
            console.print(f"[red]• {p}[/]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
