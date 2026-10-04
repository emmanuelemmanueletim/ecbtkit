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
        f'''from ecbtkit import CBT

app = CBT()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
'''
    )
    (target / ".env").write_text(
        f"ECBT_APP_NAME={name}\n"
        "ECBT_DEBUG=true\n"
        "ECBT_DATABASE_URL=sqlite:///./ecbtkit.db\n"
        "ECBT_SECRET_KEY=change-me-to-a-long-random-string-please\n"
        "ECBT_CORS_ORIGINS=*\n"
    )
    (target / "requirements.txt").write_text("ecbtkit>=0.1.0\n")
    console.print(Panel.fit(
        f"[green]Created[/] {target}\n\n  cd {name}\n  pip install -e /path/to/ecbtkit\n  python main.py",
        title="eCBTKit",
    ))


@app.command()
def dev(host: str = "127.0.0.1", port: int = 8000):
    from ecbtkit import CBT
    from ecbtkit.core.config import get_settings
    get_settings().database_auto_create = True
    console.print(f"[green]Starting[/] http://{host}:{port}/docs")
    CBT().run(host=host, port=port)


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
    full_name: str = typer.Option("Administrator", prompt=True),
):
    from ecbtkit.db.base import create_all_tables, init_db, session_scope
    from ecbtkit.models.user import User, UserRole
    from ecbtkit.security.passwords import hash_password, validate_password_strength

    validate_password_strength(password)
    init_db()
    create_all_tables()
    with session_scope() as db:
        if db.query(User).filter(User.email == email.lower()).first():
            console.print("[red]Email already registered[/]")
            raise typer.Exit(1)
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.ADMINISTRATOR,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        console.print(f"[green]Administrator created:[/] {email}")


@app.command()
def migrate():
    """Create tables and apply bundled additive database upgrades."""
    from ecbtkit.db.base import create_all_tables, init_db
    init_db()
    create_all_tables()
    console.print("[green]Database schema initialized and bundled upgrades applied[/]")


if __name__ == "__main__":
    app()
