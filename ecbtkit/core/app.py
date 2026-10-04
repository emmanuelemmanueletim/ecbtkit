"""
CBT application factory — Starlette-based, FastAPI-independent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.responses import HTMLResponse

from ecbtkit.core.config import Settings, get_settings, set_settings
from ecbtkit.ops.production import validate_production_settings
import logging
_log = logging.getLogger('ecbtkit')
from ecbtkit.db.base import create_all_tables, init_db
from ecbtkit.http.routes_auth import auth_routes
from ecbtkit.http.routes_core import core_routes
from ecbtkit.http.responses import APIResponse, SecurityHeadersMiddleware


DOCS_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>{title} — API Docs</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({{
    url: '{openapi_url}',
    dom_id: '#swagger-ui',
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: "BaseLayout"
  }})
</script>
</body>
</html>
"""


def _build_openapi(settings: Settings) -> dict:
    """Minimal OpenAPI 3 document for Swagger UI."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": settings.app_name,
            "version": settings.app_version,
            "description": "Starlette based CBT and online examination API. Authenticate with a bearer access token.",
        },
        "servers": [{"url": settings.api_prefix}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
        "security": [{"bearerAuth": []}],
        "paths": {
            "/health": {"get": {"tags": ["Health"], "summary": "Health check", "security": [], "responses": {"200": {"description": "OK"}}}},
            "/health/database": {"get": {"tags": ["Health"], "summary": "Database health", "security": [], "responses": {"200": {"description": "OK"}}}},
            "/auth/signup": {"post": {"tags": ["Authentication"], "summary": "Sign up", "security": [], "responses": {"201": {"description": "Created"}}}},
            "/auth/register": {"post": {"tags": ["Authentication"], "summary": "Register alias", "security": [], "responses": {"201": {"description": "Created"}}}},
            "/auth/login": {"post": {"tags": ["Authentication"], "summary": "Login", "security": [], "responses": {"200": {"description": "Tokens"}}}},
            "/auth/refresh": {"post": {"tags": ["Authentication"], "summary": "Refresh tokens", "security": [], "responses": {"200": {"description": "Tokens"}}}},
            "/auth/me": {"get": {"tags": ["Authentication"], "summary": "Current user", "responses": {"200": {"description": "User"}}}},
            "/auth/logout": {"post": {"tags": ["Authentication"], "summary": "Revoke sessions", "responses": {"200": {"description": "OK"}}}},
            "/auth/change-password": {"post": {"tags": ["Authentication"], "summary": "Change password", "responses": {"200": {"description": "OK"}}}},
            "/auth/forgot-password": {"post": {"tags": ["Authentication"], "summary": "Request password reset", "security": [], "responses": {"200": {"description": "OK"}}}},
            "/auth/reset-password": {"post": {"tags": ["Authentication"], "summary": "Reset password with token", "security": [], "responses": {"200": {"description": "OK"}}}},
            "/subjects": {
                "get": {"tags": ["Questions"], "summary": "List subjects", "security": [], "responses": {"200": {"description": "OK"}}},
                "post": {"tags": ["Questions"], "summary": "Create subject", "responses": {"201": {"description": "Created"}}},
            },
            "/topics": {"post": {"tags": ["Questions"], "summary": "Create topic", "responses": {"201": {"description": "Created"}}}},
            "/questions": {
                "get": {"tags": ["Questions"], "summary": "List questions", "responses": {"200": {"description": "OK"}}},
                "post": {"tags": ["Questions"], "summary": "Create question", "responses": {"201": {"description": "Created"}}},
            },
            "/questions/{question_id}": {"get": {"tags": ["Questions"], "summary": "Get question", "responses": {"200": {"description": "OK"}}}},
            "/exams": {
                "get": {"tags": ["Examinations"], "summary": "List exams", "responses": {"200": {"description": "OK"}}},
                "post": {"tags": ["Examinations"], "summary": "Create exam", "responses": {"201": {"description": "Created"}}},
            },
            "/exams/{exam_id}/publish": {"post": {"tags": ["Examinations"], "summary": "Publish exam", "responses": {"200": {"description": "OK"}}}},
            "/exams/{exam_id}/start": {"post": {"tags": ["Attempts"], "summary": "Start attempt", "responses": {"201": {"description": "Attempt"}}}},
            "/attempts/{attempt_id}/answers": {"post": {"tags": ["Attempts"], "summary": "Submit answer", "responses": {"200": {"description": "OK"}}}},
            "/attempts/{attempt_id}/submit": {"post": {"tags": ["Attempts"], "summary": "Submit attempt", "responses": {"200": {"description": "Result"}}}},
            "/attempts/{attempt_id}/answers/{question_id}": {"delete": {"tags": ["Attempts"], "summary": "Clear answer", "responses": {"204": {"description": "Deleted"}}}},
        },
    }


class CBT:
    """
    Main eCBTKit application.

    Usage::

        from ecbtkit import CBT
        app = CBT()
        app.run()
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        title: Optional[str] = None,
        create_tables: bool = True,
    ):
        self.settings = set_settings(settings) if settings is not None else get_settings()
        _problems = validate_production_settings(self.settings)
        for _p in _problems:
            _log.warning('production.check: %s', _p)
        if _problems and self.settings.is_production:
            raise RuntimeError('Unsafe production config: ' + '; '.join(_problems))
        self.settings.validate()
        if title:
            self.settings.app_name = title

        init_db(self.settings.database_url, self.settings.database_echo)
        if create_tables and self.settings.database_auto_create:
            create_all_tables()
        elif create_tables and not self.settings.database_auto_create:
            from ecbtkit.db.base import tables_exist
            if not tables_exist():
                raise RuntimeError(
                    "Database tables are missing. Run `ecbt migrate` "
                    "or set ECBT_DATABASE_AUTO_CREATE=true for local development "
                    "(or use `ecbt dev`)."
                )

        api_routes = list(auth_routes) + list(core_routes)

        async def exception_handler(request, exc):
            from ecbtkit.core.exceptions import ECBTError
            from ecbtkit.http.responses import error_response, internal_error_response
            if isinstance(exc, ECBTError):
                return error_response(exc)
            return internal_error_response(self.settings.debug, str(exc))

        async def openapi_endpoint(request):
            return APIResponse(self.openapi_schema)

        async def docs_endpoint(request):
            html = DOCS_HTML.format(
                title=self.settings.app_name,
                openapi_url=f"{self.settings.api_prefix}/openapi.json",
            )
            return HTMLResponse(html)

        routes = [
            Mount(self.settings.api_prefix, routes=api_routes + [
                Route("/openapi.json", openapi_endpoint, methods=["GET"]),
            ]),
            Route(self.settings.docs_url, docs_endpoint, methods=["GET"]),
            Route("/", docs_endpoint, methods=["GET"]),
        ]

        middleware = [
            Middleware(SecurityHeadersMiddleware),
            Middleware(
                CORSMiddleware,
                allow_origins=self.settings.cors_origins,
                allow_credentials=self.settings.cors_allow_credentials,
                allow_methods=self.settings.cors_allow_methods,
                allow_headers=self.settings.cors_allow_headers,
            ),
        ]

        self._app = Starlette(routes=routes, middleware=middleware, exception_handlers={Exception: exception_handler})
        self._exams: Dict[str, Any] = {}

    @property
    def openapi_schema(self) -> dict:
        return _build_openapi(self.settings)

    @property
    def app(self):
        """Underlying Starlette ASGI application."""
        return self._app

    def __call__(self, scope, receive, send):
        return self._app(scope, receive, send)

    def exam(self, name: str, **kwargs: Any) -> "ExamBuilder":
        builder = ExamBuilder(name=name, **kwargs)
        self._exams[name] = builder.to_dict()
        return builder


    def add_route(self, path: str, endpoint, methods: list | None = None, **kwargs):
        """Mount a custom route on the API prefix."""
        from starlette.routing import Route
        methods = methods or ["GET"]
        full = f"{self.settings.api_prefix.rstrip('/')}/{path.lstrip('/')}"
        self._app.routes.insert(0, Route(full, endpoint, methods=methods, **kwargs))
        return self

    def add_middleware(self, middleware_cls, **kwargs):
        """Add Starlette middleware."""
        self._app.add_middleware(middleware_cls, **kwargs)
        return self

    def include_router(self, routes: list, prefix: str = ""):
        """Include a list of Starlette Route objects under optional prefix."""
        from starlette.routing import Mount
        if prefix:
            self._app.routes.insert(0, Mount(prefix, routes=routes))
        else:
            for r in routes:
                self._app.routes.insert(0, r)
        return self

    def run(self, host: Optional[str] = None, port: Optional[int] = None, **kwargs: Any) -> None:
        import uvicorn
        uvicorn.run(
            self._app,
            host=host or self.settings.host,
            port=port or self.settings.port,
            **kwargs,
        )


class ExamBuilder:
    def __init__(self, name: str, **kwargs: Any):
        self.name = name
        self.config: Dict[str, Any] = {"title": name, **kwargs}
        self._selection: Dict[str, Any] = {}

    def select_questions(
        self,
        subject: Optional[str] = None,
        topics: Optional[Dict[str, int]] = None,
        difficulty: Optional[Dict[str, int]] = None,
        tags: Optional[List[str]] = None,
    ) -> "ExamBuilder":
        rules: Dict[str, Any] = {}
        if subject:
            rules["subject"] = subject
            self.config["subject"] = subject
        if topics:
            rules["topics"] = topics
        if difficulty:
            rules["difficulty"] = difficulty
        if tags:
            rules["tags"] = tags
        self._selection = rules
        self.config["selection_rules"] = rules
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {**self.config, "selection_rules": self._selection}
