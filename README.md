# eCBTKit

**A production-ready Python framework for CBT & online examination APIs**

> **Build the CBT API, not the CBT engine.**

**Version:** 0.1.0  
**Author:** Emmanuel Emmanuel Etim  
**License:** MIT  
**Repository:** https://github.com/emmanuelemmanueletim/ecbtkit  
**Author email:** emmanuel224etim089@gmail.com  

**Independent of FastAPI** — built on Starlette ASGI.  
**Strong auth** — Argon2id, lockout, refresh tokens, password policy.  
**Multi-database** — SQLite, PostgreSQL, MySQL, MongoDB.

---

## Install

```bash
pip install -e .
# or
pip install -r requirements.txt
```

Optional drivers:

```bash
pip install psycopg2-binary          # PostgreSQL
pip install pymysql cryptography     # MySQL
pip install pymongo                  # MongoDB
```

## Quick start

```python
from ecbtkit import CBT

app = CBT()
app.run(host="127.0.0.1", port=8000)
```

Open **http://127.0.0.1:8000/docs**

## Auth that stands out

| Feature | Included |
|---------|----------|
| Argon2id password hashing | ✅ |
| Password strength policy | ✅ |
| Brute-force lockout | ✅ |
| Access + refresh tokens | ✅ |
| Password reset flow | ✅ |
| Auth rate limiting | ✅ |
| Security response headers | ✅ |
| No user enumeration | ✅ |

```http
POST /api/v1/auth/signup
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
POST /api/v1/auth/change-password
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
```

## Databases

```env
# SQLite (dev)
ECBT_DATABASE_URL=sqlite:///./ecbtkit.db

# PostgreSQL
ECBT_DATABASE_URL=postgresql://user:pass@localhost:5432/ecbt

# MySQL
ECBT_DATABASE_URL=mysql://user:pass@localhost:3306/ecbt

# MongoDB
ECBT_DATABASE_URL=mongodb://localhost:27017/ecbt
ECBT_DATABASE_BACKEND=mongo
```

## Examination engine

Question bank · selection rules · deterministic randomization · server-side timer ·  
answer submission · automatic marking · negative marking · grading · result visibility ·  
structured errors · role-based access

## Docs

- [Authentication](docs/auth/overview.md)
- [Security](docs/security/overview.md)
- [Database](docs/database/overview.md)
- [First project](docs/guides/first-project.md)
- [API overview](docs/api/overview.md)

## Architecture

```
eCBTKit (independent)
├── Domain engine (no HTTP)
├── Auth service (no HTTP)
├── Security (passwords, tokens, rate limit, headers)
├── DB adapters (SQLAlchemy · Mongo)
└── HTTP layer (Starlette ASGI — not FastAPI)
```

## License

MIT © Emmanuel Emmanuel Etim
