# Security

## Correct-answer protection

During an active attempt the API **never** returns:

- which option is correct
- explanations that reveal the answer
- internal marking metadata

## Server-authoritative timer

The frontend may display a countdown, but the backend is the sole source of truth for expiration. When the deadline is reached the attempt is finalized automatically.

## Attempt integrity

- A candidate cannot modify another candidate’s attempt
- Questions not assigned to the attempt cannot be answered
- Score, assigned questions, and expiration cannot be altered by the client
- Critical operations run inside database transactions

## Authentication

JWT bearer tokens are used by default. Integrate your own identity provider by replacing or extending the auth dependencies.

## Recommendations for production

- Set a strong `ECBT_SECRET_KEY`
- Restrict `ECBT_CORS_ORIGINS`
- Use PostgreSQL or MySQL instead of SQLite
- Enable HTTPS
- Review rate-limiting configuration
