"""Authentication dependency for administrative routes.

Supports:
1. X-Admin-Token header matching settings.admin_secret_token or admin_password
2. Authorization: Bearer <token> matching settings.admin_secret_token or admin_password
3. HTTP Basic Authentication (username:password) matching settings.admin_username / admin_password
"""

from __future__ import annotations

import secrets
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import get_settings

security = HTTPBasic(auto_error=False)


def verify_admin_token(token: str) -> bool:
    """Return True if token matches configured admin secret or password."""
    settings = get_settings()
    if not token or not token.strip():
        return False
    candidate = token.strip()
    valid_tokens = [settings.admin_secret_token, settings.admin_password]
    for vt in valid_tokens:
        if secrets.compare_digest(candidate, vt):
            return True
    return False


def require_admin(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> str:
    """Enforce authentication (Token Secret or Basic Auth) if ADMIN_AUTH_ENABLED is True."""
    settings = get_settings()
    if not settings.admin_auth_enabled:
        return "anonymous_admin"

    # 1. Check X-Admin-Token header
    token_header = request.headers.get("X-Admin-Token")
    if token_header and verify_admin_token(token_header):
        return "admin_token_user"

    # 2. Check Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header.split(" ", 1)[1].strip()
        if verify_admin_token(bearer_token):
            return "admin_token_user"

    # 3. Check cookies (convenience for browser navigation)
    cookie_token = request.cookies.get("mti_admin_token")
    if cookie_token and verify_admin_token(cookie_token):
        return "admin_token_user"

    # 4. Check HTTP Basic
    if credentials is not None:
        correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
        correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
        if correct_username and correct_password:
            return credentials.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin token secret or credentials required",
        headers={"WWW-Authenticate": 'Basic realm="MTI Admin Console"'},
    )
