# Production operations

## 1. Configuration check

```python
from ecbtkit.ops import assert_production_safe
assert_production_safe()  # raises if unsafe
```

Rejects in production:

- `ECBT_DEBUG=true`
- Weak / default `ECBT_SECRET_KEY`
- SQLite as primary DB
- CORS `*` with credentials
- Mail enabled without from-address / provider

## 2. Shared rate limiting (Redis)

```env
ECBT_REDIS_URL=redis://localhost:6379/0
ECBT_RATE_LIMIT_ENABLED=true
ECBT_AUTH_RATE_LIMIT_REQUESTS=10
```

If Redis is down, the framework **falls back to in-memory** limits (fail-safe).

## 3. Database migrations (Alembic)

```bash
# Generate migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply on deploy
alembic upgrade head
```

Do **not** rely on auto `create_all` in production. Run migrations as a deploy step.

```env
ECBT_DATABASE_URL=postgresql://user:pass@db:5432/ecbt
```

## 4. Secrets

- Load from environment or your host’s secret manager  
- Never commit `.env` with real secrets  
- Rotate `ECBT_SECRET_KEY` carefully (invalidates tokens)  
- Logs never include passwords, tokens, or reset links  

## 5. Health checks

- `GET /api/v1/health` — liveness  
- `GET /api/v1/health/database` — readiness (DB connectivity)  

Use these for load balancers and orchestrators.

## 6. Deployment checklist

- [ ] `ECBT_ENVIRONMENT=production`  
- [ ] Strong `ECBT_SECRET_KEY` (≥32 random chars)  
- [ ] PostgreSQL or MySQL  
- [ ] `ECBT_DEBUG=false`  
- [ ] Explicit CORS origins  
- [ ] HTTPS terminator  
- [ ] Mail provider configured  
- [ ] `ECBT_MAIL_LINK_BASE_URL=https://your-frontend`  
- [ ] Redis for multi-worker rate limits  
- [ ] `alembic upgrade head` on deploy  
- [ ] Automated DB backups + restore tested  
- [ ] Multiple uvicorn workers behind a proxy  

```bash
uvicorn ecbtkit_app:app --host 0.0.0.0 --port 8000 --workers 4
```
