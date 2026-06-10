import httpx
from pydantic import BaseModel

from app.core.config import settings

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekMessage(BaseModel):
    role: str
    content: str


class DeepSeekChoice(BaseModel):
    message: DeepSeekMessage


class DeepSeekChatResponse(BaseModel):
    choices: list[DeepSeekChoice]


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
):
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature
        if temperature is not None
        else settings.llm_temperature,
    }

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
        )

    _ = response.raise_for_status()
    data = DeepSeekChatResponse.model_validate(response.json())

    if not data.choices:
        raise RuntimeError("Deepseek response has no choices")

    return data.choices[0].message.content


async def chat_with_deepseek(message: str) -> str:
    return await chat_completion(
        messages=[
            {"role": "system", "content": "你是清商项目中的宋词助手。"},
            {"role": "user", "content": message},
        ]
    )
