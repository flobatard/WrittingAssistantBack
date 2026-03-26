from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt

from app.core.config import Settings, get_settings

_jwks_cache: dict[str, Any] | None = None


async def _get_jwks(issuer_url: str) -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        discovery = await client.get(discovery_url)
        discovery.raise_for_status()
        jwks_url = discovery.json()["jwks_uri"]
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


async def get_current_user_sub(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token d'authentification manquant")

    token = authorization.removeprefix("Bearer ")

    try:
        jwks = await _get_jwks(settings.OIDC_ISSUER_URL)
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
        print("ER")
        raise HTTPException(status_code=503, detail=f"Impossible de joindre l'OIDC provider : {e}")

    sub: str | None = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Claim 'sub' absent du token")

    return sub
