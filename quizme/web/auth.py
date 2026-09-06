"""Single-identity auth (AD-10, FR-46).

Platform edge does the real work: App Service / Functions "Easy Auth" (Entra ID)
with *assignment required* on the enterprise app. This module is belt-and-braces:
it reads the ``X-MS-CLIENT-PRINCIPAL`` header Easy Auth injects and checks the
principal against a one-entry allowlist. If the header is absent (someone bypassed
the edge) the request is rejected.
"""

from __future__ import annotations

import base64
import binascii
import json
import os

from fastapi import Header, HTTPException, status

_ALLOWED = os.environ.get("WEB_ALLOWED_PRINCIPAL", "")


def _principal_id(encoded: str) -> str | None:
    try:
        payload = json.loads(base64.b64decode(encoded))
    except (binascii.Error, ValueError):
        return None
    claims = {c.get("typ"): c.get("val") for c in payload.get("claims", [])}
    return (
        claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier")
        or claims.get("preferred_username")
        or payload.get("userId")
    )


async def require_user(
    x_ms_client_principal: str | None = Header(default=None),
) -> str:
    """FastAPI dependency. Returns the principal id or raises 401/403."""
    if not x_ms_client_principal:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no authenticated principal")
    principal = _principal_id(x_ms_client_principal)
    if not principal:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unreadable principal")
    if _ALLOWED and principal != _ALLOWED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "principal not allowed")
    return principal
