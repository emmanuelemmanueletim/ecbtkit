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

## MongoDB (optional)

```bash
pip install pymongo
```

```env
ECBT_DATABASE_URL=mongodb://localhost:27017/ecbt
ECBT_DATABASE_BACKEND=mongo
```

Mongo is available via `ecbtkit.adapters.mongo.get_mongo_db()`.  
The full relational exam engine (attempts, FKs, transactions) is optimized for the **SQL** path. Use Mongo for document-oriented question banks or analytics stores when needed.

## Auto detection

```env
ECBT_DATABASE_BACKEND=auto   # default — inspects URL scheme
```

## Transactions

Critical operations (submit attempt, mark, create result) run inside SQL transactions so you never get a score without a result row (or the reverse).
