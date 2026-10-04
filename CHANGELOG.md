# Changelog

## [0.1.0] — 2026-10-04

### Added
- CBT domain engine: questions, exams, attempts, server-side timer, marking, scoring, grading
- Starlette ASGI HTTP layer
- Strong authentication: Argon2id hashing, password policy, account lockout, access + refresh tokens
- Password change, forgot-password, reset-password flows
- Auth rate limiting and security response headers
- SQL database support: SQLite, PostgreSQL, and MySQL
- Structured error system
- OpenAPI docs at `/docs`
- CLI (`ecbt create`, `ecbt dev`, `ecbt create-admin`, `ecbt migrate`)
- Documentation: auth, security, database, guides

### Author
Emmanuel Emmanuel Etim  
Email: emmanuel224etim089@gmail.com  
Repository: https://github.com/emmanuelemmanueletim/ecbtkit

## Unreleased hardening

- Consolidated runtime API on Starlette and removed unused alternate route modules.
- Limited supported application databases to SQLAlchemy SQL backends.
- Tightened CORS defaults, response security headers, refresh-token rotation, and reset-token storage.
- Applied question tags to quota selection, validated quotas, and honored per-question marks.
- Added database constraints for one active attempt and one answer per attempt/question.
- Reclassified package maturity as Alpha pending broader verification.
