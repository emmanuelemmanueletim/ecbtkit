# eCBTKit

**An early-stage Python framework for CBT & online examination APIs**

> **Build the CBT API, not the CBT engine.**

**Version:** 0.1.0  
**Author:** Emmanuel Emmanuel Etim  
**License:** MIT  
**Repository:** https://github.com/emmanuelemmanueletim/ecbtkit  
**Author email:** emmanuel224etim089@gmail.com  

**Starlette ASGI** — no FastAPI dependency.  
**Strong auth** — Argon2id, lockout, refresh tokens, password policy.  
**SQL databases** — SQLite, PostgreSQL, and MySQL through SQLAlchemy.

---

## Install

```bash
pip install -e .
# or
pip install -r requirements.txt
```

The project is Alpha. Run `ecbt migrate` before starting the application; tables are not created automatically. `ecbt dev` enables development-only automatic table creation.

Optional drivers:

```bash
pip install psycopg2-binary          # PostgreSQL
pip install pymysql cryptography     # MySQL
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

```

The examination engine currently supports SQL databases only. MongoDB is not a supported application backend. Set `ECBT_CORS_ORIGINS` to a comma-separated allowlist when browser clients need cross-origin access; credentials are disabled by default.

**Maturity:** Alpha. Run multiple workers only with PostgreSQL/MySQL and a shared rate limiter at the proxy or gateway. Password reset creates a one-time token, but applications must deliver it through their email system; this package does not send email.

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
├── SQL persistence (SQLAlchemy)
└── HTTP layer (Starlette ASGI)
```

## License

MIT © Emmanuel Emmanuel Etim


## Email (simple)

```env
ECBT_MAIL_ENABLED=true
ECBT_MAIL_PROVIDER=sendgrid
ECBT_MAIL_API_KEY=SG.xxx
ECBT_MAIL_FROM=noreply@yourdomain.com
ECBT_MAIL_LINK_BASE_URL=https://app.yourdomain.com
```

See [docs/mail/overview.md](docs/mail/overview.md).

## Production

See [docs/ops/production.md](docs/ops/production.md).
