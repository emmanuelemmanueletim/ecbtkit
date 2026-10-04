# Changelog

## [0.1.0] — 2026-10-04

### Added
- CBT domain engine: questions, exams, attempts, timers, marking, scoring, grading
- Starlette HTTP layer (FastAPI-independent)
- Strong auth: Argon2id, lockout, access + refresh tokens, password policy
- **Email delivery layer** — provider presets (SMTP, SES, SendGrid, Mailgun, Postmark, Resend, Gmail, Office365)
- Verification & password-reset emails; tokens never returned in HTTP responses
- Async mail so signup/reset is not blocked by SMTP
- Redis-backed shared rate limiting with in-memory fallback
- Alembic migration support
- Production configuration validation
- Multi-database: SQLite, PostgreSQL, MySQL, MongoDB adapter
- Structured errors, security headers, OpenAPI docs

### Author
Emmanuel Emmanuel Etim  
Email: emmanuel224etim089@gmail.com  
Repository: https://github.com/emmanuelemmanueletim/ecbtkit
