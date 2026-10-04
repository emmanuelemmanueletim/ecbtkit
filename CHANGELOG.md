# Changelog

## [0.1.0] — 2026-10-04

### Framework maturity
- Starlette-based CBT API framework (not a hosted product)
- Alembic-first migrations (`ecbt migrate` → `alembic upgrade head`)
- Startup never alters production schema
- Email verification + password reset with hashed, single-use tokens
- Verification tokens separated from reset tokens
- No access tokens issued until verification succeeds (when required)
- Redis required for rate limiting in production (no silent memory fallback)
- Production config validation (secrets, CORS, SQLite, mail HTTPS links, Redis)
- Extension points: custom routes, middleware, injectable engine, email providers
- Candidate-only public signup; staff via `ecbt create-admin`
- Refresh tokens single-use; sessions revoked on password change/reset/logout

### Author
Emmanuel Emmanuel Etim  
emmanuel224etim089@gmail.com  
https://github.com/emmanuelemmanueletim/ecbtkit
