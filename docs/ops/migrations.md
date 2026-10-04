# Database migrations

eCBTKit uses **Alembic**. Schema changes are versioned files — startup does **not** alter production tables.

## Install

```bash
pip install alembic
# or
pip install ecbtkit[alembic]
```

## Apply migrations

```bash
# Recommended
ecbt migrate

# Or directly
alembic upgrade head
```

## Fresh development database

```bash
# Option A — Alembic (preferred)
ecbt migrate

# Option B — local only (ECBT_DATABASE_AUTO_CREATE=true)
ecbt dev
```

## Create a new migration after model changes

```bash
alembic revision --autogenerate -m "add column foo"
# Review the generated file under alembic/versions/
alembic upgrade head
```

## Rollback

```bash
alembic downgrade -1
```

## Production

1. Set `ECBT_DATABASE_AUTO_CREATE=false` (default)
2. Run `ecbt migrate` (or `alembic upgrade head`) as a **deploy step** before starting workers
3. Never rely on `create_all` in production
