# Email delivery

eCBTKit sends **verification** and **password-reset** emails for you.  
You only choose a provider and set keys — no custom mail code.

## Quick setup

### SendGrid

```env
ECBT_MAIL_ENABLED=true
ECBT_MAIL_PROVIDER=sendgrid
ECBT_MAIL_API_KEY=SG.xxxxxxxx
ECBT_MAIL_FROM=noreply@yourdomain.com
ECBT_MAIL_FROM_NAME=My CBT App
ECBT_MAIL_LINK_BASE_URL=https://app.yourdomain.com
```

### Amazon SES (SMTP)

```env
ECBT_MAIL_ENABLED=true
ECBT_MAIL_PROVIDER=ses
ECBT_MAIL_REGION=us-east-1
ECBT_MAIL_USERNAME=AKIA...
ECBT_MAIL_PASSWORD=smtp-secret
ECBT_MAIL_FROM=noreply@yourdomain.com
ECBT_MAIL_LINK_BASE_URL=https://app.yourdomain.com
```

### Mailgun / Postmark / Resend

```env
ECBT_MAIL_PROVIDER=mailgun   # or postmark | resend
ECBT_MAIL_API_KEY=key-xxx    # or SMTP password
ECBT_MAIL_USERNAME=...       # if required by provider
ECBT_MAIL_FROM=noreply@yourdomain.com
```

### Any SMTP relay

```env
ECBT_MAIL_PROVIDER=smtp
ECBT_MAIL_HOST=mail.company.com
ECBT_MAIL_PORT=587
ECBT_MAIL_USERNAME=user
ECBT_MAIL_PASSWORD=secret
ECBT_MAIL_FROM=noreply@company.com
ECBT_MAIL_USE_TLS=true
```

### Development (no email)

```env
ECBT_MAIL_ENABLED=false
# or ECBT_MAIL_PROVIDER=null
```

## What the framework sends

| Event | Email |
|-------|--------|
| Signup (when verification required) | Verification link |
| Forgot password | Reset link (token **never** in HTTP response) |
| Password changed | Security notice |
| New sign-in | Optional alert with IP |

Links use `ECBT_MAIL_LINK_BASE_URL`:

- `{base}/verify-email?token=...`
- `{base}/reset-password?token=...`

Your frontend should read `token` from the query string and call:

- `POST /api/v1/auth/reset-password` with `{ "token", "new_password" }`

## Behaviour

- **Async by default** (`ECBT_MAIL_ASYNC=true`) — signup/reset is not blocked by SMTP  
- Tokens stored as **hashes** only  
- Logs mask recipient emails and **never** log tokens or full reset links  
- Provider failures are logged; they do not crash the request  

## Domain reputation (production)

Configure for your sending domain:

1. **SPF** — allow your provider’s servers  
2. **DKIM** — sign messages (provider dashboard)  
3. **DMARC** — policy for spoofing protection  

## Supported providers

| Provider | `ECBT_MAIL_PROVIDER` | Auth |
|----------|----------------------|------|
| Disabled | `null` | — |
| Custom SMTP | `smtp` | host + user/pass |
| Amazon SES | `ses` | SMTP user/pass + region |
| SendGrid | `sendgrid` | API key |
| Mailgun | `mailgun` | API key / SMTP |
| Postmark | `postmark` | API key / SMTP |
| Resend | `resend` | API key |
| Gmail | `gmail` | app password or OAuth SMTP |
| Microsoft 365 | `office365` | SMTP / OAuth |


## Delivery durability

Default async sending uses a **process-local thread pool**. If the worker process restarts before SMTP completes, a queued message may be lost.

For production systems that must not lose mail:

1. Set `ECBT_MAIL_ASYNC=false` for synchronous send (signup waits on SMTP), or
2. Provide a custom `EmailProvider` that enqueues to Redis/SQS/Celery/your outbox, or
3. Handle delivery in the application layer after framework token creation.
