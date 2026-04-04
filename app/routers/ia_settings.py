import openai
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.dependancies import ProviderConfig, get_provider_config

router = APIRouter(tags=["ia-settings"])

_PROVIDER_BASE_URLS: dict[str, str] = {
    "openai":      "https://api.openai.com/v1",
    "mistral":     "https://api.mistral.ai/v1",
    "huggingface": "https://router.huggingface.co/v1",
}


class ModelsResponse(BaseModel):
    models: list[str]


@router.get("/models", response_model=ModelsResponse)
async def list_models(config: ProviderConfig = Depends(get_provider_config)) -> ModelsResponse:
    provider = config.provider.lower()
    match provider:
        case "openai" | "mistral" | "huggingface":
            return await _list_openai_compatible(_PROVIDER_BASE_URLS[provider], config.api_key)
        case "url":
            return await _list_openai_compatible(config.url, config.api_key)
        case "ollama":
            return await _list_ollama(config.url)
        case "google":
            return await _list_google(config.api_key)
        case "anthropic":
            return await _list_anthropic(config.api_key)
        case _:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: '{provider}'. Supported: openai, mistral, huggingface, url, ollama, google, anthropic.",
            )


async def _list_openai_compatible(base_url: str | None, api_key: str | None) -> ModelsResponse:
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Api-Url header is required for this provider.",
        )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Api-Key header is required for this provider.",
        )
    try:
        client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        response = await client.models.list()
        return ModelsResponse(models=[m.id for m in response.data])
    except openai.AuthenticationError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    except openai.APIConnectionError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the provider API.")
    except openai.APIStatusError as exc:
        raise HTTPException(status_code=exc.status_code, detail=f"Provider API error: {exc.message}")


async def _list_ollama(base_url: str | None) -> ModelsResponse:
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Api-Url header is required for the ollama provider.",
        )
    url = base_url.rstrip("/") + "/api/tags"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"Ollama error: {exc.response.text}")
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the Ollama instance.")
    data = response.json()
    return ModelsResponse(models=[m["name"] for m in data.get("models", [])])


async def _list_google(api_key: str | None) -> ModelsResponse:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Api-Key header is required for the google provider.",
        )
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"Google API error: {exc.response.text}")
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the Google API.")
    data = response.json()
    models = [
        m["name"].removeprefix("models/")
        for m in data.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    return ModelsResponse(models=models)


async def _list_anthropic(api_key: str | None) -> ModelsResponse:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Api-Key header is required for the anthropic provider.",
        )
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://api.anthropic.com/v1/models", headers=headers, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"Anthropic API error: {exc.response.text}")
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the Anthropic API.")
    data = response.json()
    return ModelsResponse(models=[m["id"] for m in data.get("data", [])])
