# Extending eCBTKit

eCBTKit is a library your application embeds — not a hosted platform.

## Custom routes

```python
from ecbtkit import CBT

async def hello(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"hello": "world"})

app = CBT()
app.add_route("/custom/hello", hello, methods=["GET"])
app.run()
```

## Custom middleware

```python
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = "..."
        return response

app = CBT()
app.add_middleware(RequestIdMiddleware)
```

## Inject your own SQLAlchemy engine

```python
from sqlalchemy import create_engine
from ecbtkit.db.base import configure_engine, init_db
from ecbtkit import CBT

engine = create_engine("postgresql://...")
configure_engine(engine)
app = CBT(create_tables=False)
```

## Custom email provider

```python
from ecbtkit.mail.base import EmailProvider, EmailMessage, SendResult
from ecbtkit.mail.service import EmailService

class MyProvider(EmailProvider):
    name = "myprovider"
    def send(self, message: EmailMessage) -> SendResult:
        # call your API
        return SendResult(ok=True, provider=self.name)

mail = EmailService(provider=MyProvider())
# pass into AuthService(db, mail=mail) in your own wiring
```

## Mount into an existing Starlette app

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from ecbtkit import CBT

cbt = CBT(create_tables=False)
host = Starlette(routes=[
    Mount("/", app=cbt.app),
])
```

## Public vs internal

| Public API | Internal |
|------------|----------|
| `CBT`, `Settings` | `ecbtkit.http.*` route handlers |
| `AuthService` | private helpers |
| `EmailService`, `EmailProvider` | mail SMTP details |
| `AttemptService`, engines | model private columns |
| `ecbtkit.ops` validators | — |

Deployment concerns (HTTPS, backups, workers, secret managers) belong to the **application operator**, not the framework. See `docs/ops/production.md`.
