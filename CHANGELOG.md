# Changelog

## [0.1.0] — 2026-10-04

### Added
- CBT domain engine: questions, exams, attempts, server-side timer, marking, scoring, grading
- **FastAPI-independent** HTTP layer (Starlette ASGI)
- Strong authentication: Argon2id hashing, password policy, account lockout, access + refresh tokens
- Password change, forgot-password, reset-password flows
- Auth rate limiting and security response headers
- Multi-database support: SQLite, PostgreSQL, MySQL, MongoDB adapter
- Structured error system
- OpenAPI docs at `/docs`
- CLI (`ecbt create`, `ecbt dev`, `ecbt create-admin`, `ecbt migrate`)
- Documentation: auth, security, database, guides

### Author
Emmanuel Emmanuel Etim  
Email: emmanuel224etim089@gmail.com  
Repository: https://github.com/emmanuelemmanueletim/ecbtkit
