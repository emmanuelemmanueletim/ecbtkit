# Database support

eCBTKit supports multiple databases through a unified configuration URL.

## SQL backends (default)

Powered by SQLAlchemy 2.x.

| Database | URL example | Extra install |
|----------|-------------|---------------|
| **SQLite** | `sqlite:///./ecbtkit.db` | (built-in) |
| **PostgreSQL** | `postgresql://user:pass@localhost:5432/ecbt` | `pip install psycopg2-binary` |
| **MySQL** | `mysql://user:pass@localhost:3306/ecbt` | `pip install pymysql cryptography` |

Also accepted:

- `postgres://...` → normalized to `postgresql://`  
- `mysql://...` → normalized to `mysql+pymysql://`  

```env
ECBT_DATABASE_URL=postgresql://ecbt:secret@db:5432/ecbt
```

MongoDB is not currently supported as an application backend. The exam and attempt services depend on SQL transactions and relational constraints.

## Auto detection

```env
ECBT_DATABASE_BACKEND=auto   # detects SQL URL schemes
```

## Transactions

Critical operations (submit attempt, mark, create result) run inside SQL transactions. A unique constraint prevents duplicate result rows, answer keys prevent duplicate answer rows, and a partial unique index prevents more than one active attempt per candidate and exam.
