from __future__ import annotations

import httpx

from app.core.config import settings


class LLMClientError(RuntimeError):
    pass


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> str:
    if not settings.llm_api_key:
        raise LLMClientError("缺少 LLM_API_KEY，请在 .env 中配置。")

    url = f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions"

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code >= 400:
        raise LLMClientError(f"LLM 请求失败：{response.status_code} {response.text}")

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMClientError(f"LLM 返回格式异常：{data}") from exc
