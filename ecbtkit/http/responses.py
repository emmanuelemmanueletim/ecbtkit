"""JSON helpers and error response formatting."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from starlette.responses import JSONResponse, Response

from ecbtkit.core.exceptions import ECBTError
from ecbtkit.security.headers import security_headers


class APIResponse(JSONResponse):
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ):
        hdrs = security_headers()
        if headers:
            hdrs.update(headers)
        super().__init__(content=content, status_code=status_code, headers=hdrs, **kwargs)


def error_response(exc: ECBTError) -> JSONResponse:
    hdrs = security_headers()
    if hasattr(exc, "details") and isinstance(exc.details, dict) and "retry_after" in exc.details:
        hdrs["Retry-After"] = str(exc.details["retry_after"])
    return JSONResponse(content=exc.to_dict(), status_code=exc.status_code, headers=hdrs)


def internal_error_response(debug: bool = False, detail: str = "") -> JSONResponse:
    body: Dict[str, Any] = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": detail if debug and detail else "An unexpected error occurred",
            "details": {},
        }
    }
    return JSONResponse(content=body, status_code=500, headers=security_headers())
