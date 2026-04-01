from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user_sub
from app.core.config import get_settings
from app.schemas.spellcheck import SpellCheckRequest

router = APIRouter(tags=["spellcheck"])


def _languagetool_url(path: str) -> str:
    s = get_settings()
    return f"http://{s.LANGUAGETOOL_HOST}:{s.LANGUAGETOOL_PORT}{path}"


@router.post("/check", response_model=None)
async def check_text(
    payload: SpellCheckRequest,
    _sub: str = Depends(get_current_user_sub),
) -> Any:
    form_data: dict[str, str] = {
        "text": payload.text,
        "language": payload.language,
        "enabledOnly": str(payload.enabled_only).lower(),
    }
    if payload.disabled_rules:
        form_data["disabledRules"] = ",".join(payload.disabled_rules)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                _languagetool_url("/v2/check"),
                data=form_data,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"LanguageTool error: {exc.response.text}",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LanguageTool service unavailable",
            )

    return response.json()


@router.get("/languages", response_model=None)
async def list_languages(
    _sub: str = Depends(get_current_user_sub),
) -> Any:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                _languagetool_url("/v2/languages"),
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"LanguageTool error: {exc.response.text}",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LanguageTool service unavailable",
            )

    return response.json()
