"""API token authentication helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import User


TOKEN_PREFIX = "agt_"


def verify_admin_secret(secret: str | None) -> None:
    if not secret:
        raise ValueError("missing admin secret")
    if settings.app_env != "local" and settings.app_secret_key == "local-dev":
        raise ValueError("APP_SECRET_KEY must be changed outside local env")
    if not hmac.compare_digest(secret, settings.app_secret_key):
        raise ValueError("invalid admin secret")


def issue_api_token(db: Session, tenant_id: str, user_id: str) -> tuple[User, str]:
    user = db.get(User, user_id)
    if user is None or user.tenant_id != tenant_id or user.status != "active":
        raise ValueError("user not found")
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    user.api_token_hash = hash_api_token(token)
    db.commit()
    db.refresh(user)
    return user, token


def authenticate_api_token(db: Session, authorization: str | None) -> User:
    token = _extract_bearer_token(authorization)
    if token is None:
        raise ValueError("missing bearer token")
    token_hash = hash_api_token(token)
    user = db.scalars(
        select(User).where(User.api_token_hash == token_hash, User.status == "active")
    ).first()
    if user is None:
        raise ValueError("invalid bearer token")
    return user


def hash_api_token(token: str) -> str:
    return hmac.new(
        settings.app_secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
