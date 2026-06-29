"""调用兼容 OpenAI Chat Completions 协议的 LLM。"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from app.core.config import settings


# ============================================================================
# LLM 响应数据结构
# ============================================================================


class LLMClientError(RuntimeError):
    """把配置、HTTP 和响应格式错误统一成上层可处理的一种异常。"""


class LLMMessage(BaseModel):
    """LLM 响应中的一条消息。"""

    role: str
    content: str


class LLMChoice(BaseModel):
    """LLM 响应中的一个候选答案。"""

    message: LLMMessage


class LLMChatResponse(BaseModel):
    """本项目实际使用到的 Chat Completions 响应字段。"""

    choices: list[LLMChoice]


# ============================================================================
# LLM 调用
# ============================================================================


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """发送聊天请求并返回第一个候选文本。"""
    # 步骤 ① 检查必要配置（API key 缺失时提前失败，避免无用请求）
    if not settings.llm_api_key:
        raise LLMClientError("缺少 LLM_API_KEY，请在 .env 中配置。")

    # 步骤 ② 拼接 Chat Completions 请求 URL
    url = f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions"

    # 步骤 ③ 构造请求体（模型名、消息列表、温度参数）
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

    # 步骤 ④ 发送 HTTP POST 请求；超时由 settings 统一控制
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)

    # 步骤 ⑤ 校验 HTTP 状态码；非 2xx 统一转为客户端异常
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LLMClientError(
            f"LLM 请求失败：{response.status_code} {response.text}"
        ) from exc

    # 步骤 ⑥ 校验响应结构；外部响应必须先通过本地结构校验，不能直接交给业务层。
    try:
        data = LLMChatResponse.model_validate(response.json())
    except (ValueError, TypeError) as exc:
        raise LLMClientError("LLM 返回格式异常") from exc

    if not data.choices:
        raise LLMClientError("LLM 返回中没有 choices")

    return data.choices[0].message.content
