"""
Clerk JWT verification for FastAPI.
Verifies tokens using Clerk's JWKS endpoint.
"""
import time
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from loguru import logger

from app.core.config import settings

_JWKS_CACHE: dict = {}
_JWKS_FETCHED_AT: float = 0
_JWKS_TTL = 3600  # re-fetch keys every hour


def _get_clerk_jwks_url() -> str:
    issuer = settings.clerk_issuer
    return f"{issuer}/.well-known/jwks.json"


def _fetch_jwks() -> dict:
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    now = time.time()
    if _JWKS_CACHE and (now - _JWKS_FETCHED_AT) < _JWKS_TTL:
        return _JWKS_CACHE
    try:
        resp = httpx.get(_get_clerk_jwks_url(), timeout=5)
        resp.raise_for_status()
        _JWKS_CACHE = resp.json()
        _JWKS_FETCHED_AT = now
        logger.info("Clerk JWKS refreshed")
        return _JWKS_CACHE
    except Exception as exc:
        logger.warning("Failed to fetch Clerk JWKS: {e}", e=exc)
        return _JWKS_CACHE  # return stale cache on failure


def verify_clerk_token(authorization: Optional[str] = Header(default=None)) -> dict:
    """Dependency — returns the decoded Clerk JWT claims."""
    if not settings.clerk_issuer:
        # Auth not configured — return a dev stub
        return {"sub": "dev_user", "metadata": {"role": "instructor"}}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        jwks = _fetch_jwks()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def require_instructor(claims: dict = Depends(verify_clerk_token)) -> dict:
    role = (claims.get("public_metadata") or claims.get("metadata") or {}).get("role", "trainee")
    if role != "instructor":
        raise HTTPException(status_code=403, detail="Instructor access required")
    return claims


def get_user_id(claims: dict = Depends(verify_clerk_token)) -> str:
    return claims["sub"]
