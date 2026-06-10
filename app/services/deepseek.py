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


async def chat_with_deepseek(message: str) -> str:
    if not settings.deepseek_api_key:
        raise ValueError("DeepSeek API key is not set")

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是清商项目中的宋词助手。"},
            {"role": "user", "content": message},
        ],
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
        )

    _ = response.raise_for_status()
    data = DeepSeekChatResponse.model_validate(response.json())

    if not data.choices:
        raise RuntimeError("DeepSeek response has no choices")

    return data.choices[0].message.content
