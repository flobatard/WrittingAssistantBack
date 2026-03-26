import time
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings

_JWKS_TTL = 3600  # secondes

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0


async def _fetch_jwks(issuer_url: str) -> dict[str, Any]:
    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        discovery = await client.get(discovery_url)
        discovery.raise_for_status()
        jwks_url = discovery.json()["jwks_uri"]
        response = await client.get(jwks_url)
        response.raise_for_status()
        return response.json()


async def _get_jwks(issuer_url: str, force_refresh: bool = False) -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    cache_expired = (time.monotonic() - _jwks_fetched_at) >= _JWKS_TTL
    if force_refresh or _jwks_cache is None or cache_expired:
        _jwks_cache = await _fetch_jwks(issuer_url)
        _jwks_fetched_at = time.monotonic()
    return _jwks_cache


def _kid_known(token: str, jwks: dict[str, Any]) -> bool:
    """Vérifie que le kid du JWT est présent dans les JWKS. Si absent du header, on laisse passer."""
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except JWTError:
        return True  # header illisible → on laisse jwt.decode gérer l'erreur
    if kid is None:
        return True  # pas de kid → pas de rotation à gérer
    return any(key.get("kid") == kid for key in jwks.get("keys", []))


async def get_current_user_sub(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token d'authentification manquant")

    token = authorization.removeprefix("Bearer ")

    try:
        jwks = await _get_jwks(settings.OIDC_ISSUER_URL)
        if not _kid_known(token, jwks):
            jwks = await _get_jwks(settings.OIDC_ISSUER_URL, force_refresh=True)
        options = {"verify_aud": bool(settings.OIDC_AUDIENCE)}
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.OIDC_AUDIENCE or None,
            options=options,
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token invalide : {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Impossible de joindre l'OIDC provider : {e}")

    sub: str | None = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Claim 'sub' absent du token")

    return sub


async def get_optional_user_sub(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Retourne le sub OIDC si un token valide est fourni, sinon None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.removeprefix("Bearer ")

    try:
        jwks = await _get_jwks(settings.OIDC_ISSUER_URL)
        if not _kid_known(token, jwks):
            jwks = await _get_jwks(settings.OIDC_ISSUER_URL, force_refresh=True)
        options = {"verify_aud": bool(settings.OIDC_AUDIENCE)}
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.OIDC_AUDIENCE or None,
            options=options,
        )
    except (JWTError, httpx.HTTPError):
        return None

    return payload.get("sub") or None


async def resolve_user_id(sub: str | None, db: AsyncSession) -> int | None:
    """Résout le sub OIDC en user.id (int) ou None. À appeler depuis les routeurs."""
    if sub is None:
        return None
    from app.models.user import User
    result = await db.execute(select(User).where(User.oidc_sub == sub))
    user = result.scalar_one_or_none()
    return user.id if user else None
