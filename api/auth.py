"""
Optional shared-secret API key.

When ``NBT_API_KEY`` is set, every /api route except /api/auth requires the
``X-API-Key`` header. When it is unset there is NO authentication: keep the
API bound to localhost (the default) or behind an authenticating proxy.
"""

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, status


def api_key_required() -> bool:
    return bool(os.environ.get("NBT_API_KEY"))


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.environ.get("NBT_API_KEY")
    if not expected:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing or invalid X-API-Key")
