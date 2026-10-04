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
- Explicit trusted hosts and HTTPS enforcement
- Redis configured for shared production rate limits
- Account email enabled with a real delivery provider and HTTPS links
- Database pool bounds and production-safe logging

## 2. Shared rate limiting (Redis)

```env
ECBT_REDIS_URL=redis://localhost:6379/0
ECBT_RATE_LIMIT_ENABLED=true
ECBT_AUTH_RATE_LIMIT_REQUESTS=10
```

Production rate limiting uses an atomic Redis script and fails closed when Redis is unavailable. In-memory limits are used only outside production. Do not bypass this requirement in multi-worker deployments.

When TLS terminates at a reverse proxy, configure Uvicorn forwarded-header handling with only the proxy addresses you trust. Set `ECBT_TRUSTED_PROXY_HOSTS` to the proxy IPs/CIDRs only when requests can reach the app exclusively through those proxies; forwarded client IP extraction is ignored for all other peers.

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
- [ ] Explicit CORS origins and trusted hostnames
- [ ] HTTPS enforced with `ECBT_FORCE_HTTPS=true` or `ECBT_HTTPS_ENFORCED_AT_PROXY=true` at the trusted edge
- [ ] Mail enabled with a verified production provider and delivery monitoring
- [ ] `ECBT_MAIL_LINK_BASE_URL=https://your-frontend`
- [ ] Redis for atomic, shared multi-worker rate limits
- [ ] `alembic upgrade head` on deploy
- [ ] Automated DB backups + restore tested on a schedule
- [ ] Multiple Uvicorn workers behind a trusted proxy; forwarded headers limited to proxy IPs

```bash
uvicorn ecbtkit_app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Operational evidence required before high-stakes use

The library cannot certify its host environment. Before using it for a live examination, record a successful PostgreSQL migration rehearsal, Redis outage exercise, email delivery check, load/concurrency test at expected peak, backup restoration drill, and incident response contact. Monitor request errors/latency, database pool exhaustion, Redis health, mail delivery failures, and exam submission rates without logging credentials or token values.
