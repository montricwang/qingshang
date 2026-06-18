from __future__ import annotations

import httpx
from pydantic import BaseModel

from app.core.config import settings


class LLMClientError(RuntimeError):
    pass


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMChoice(BaseModel):
    message: LLMMessage


class LLMChatResponse(BaseModel):
    choices: list[LLMChoice]


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    if not settings.llm_api_key:
        raise LLMClientError("缺少 LLM_API_KEY，请在 .env 中配置。")

    url = f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions"

    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": (
            temperature if temperature is not None else settings.llm_temperature
        ),
    }

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LLMClientError(
            f"LLM 请求失败：{response.status_code} {response.text}"
        ) from exc

    try:
        data = LLMChatResponse.model_validate(response.json())
    except (ValueError, TypeError) as exc:
        raise LLMClientError("LLM 返回格式异常") from exc

    if not data.choices:
        raise LLMClientError("LLM 返回中没有 choices")

    return data.choices[0].message.content
