# Security

## Principles

1. **Server is authoritative** — timers, scores, correct answers never trusted from the client  
2. **Secrets stay server-side** — correct options never returned during an active attempt  
3. **Defence in depth** — password policy, lockout, rate limits, security headers, structured errors  
4. **Least privilege** — roles: candidate, examiner, administrator  

## Auth security

- Argon2id (or PBKDF2-SHA256) password hashing  
- Configurable password policy  
- Account lockout after failed attempts  
- Short-lived access tokens + refresh tokens  
- Rate limiting on auth routes  
- No email enumeration on login / forgot-password  

## Transport & headers

When `ECBT_SECURITY_HEADERS_ENABLED=true` (default):

- `X-Content-Type-Options: nosniff`  
- `X-Frame-Options: DENY`  
- `Referrer-Policy: strict-origin-when-cross-origin`  
- `Content-Security-Policy` (restrictive default)  
- `Strict-Transport-Security` in production  

## CORS

Set explicit origins in production:

```env
ECBT_CORS_ORIGINS=https://app.example.com
```

## Examination integrity

- Candidates cannot access another candidate’s attempt or result  
- Answers only accepted for questions assigned to the attempt  
- Expired attempts are finalized server-side  
- Marking runs only on the server  

## Production checklist

- [ ] Strong unique `ECBT_SECRET_KEY`  
- [ ] `ECBT_ENVIRONMENT=production`  
- [ ] `ECBT_DEBUG=false`  
- [ ] PostgreSQL or MySQL (not SQLite)  
- [ ] HTTPS termination  
- [ ] Restricted CORS origins  
- [ ] Email delivery for password-reset tokens (do not return tokens in API responses)  
