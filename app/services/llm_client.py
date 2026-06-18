"""调用兼容 OpenAI Chat Completions 格式的 LLM HTTP 接口。

上层业务只需要传 messages，不关心 URL、认证头、超时和响应 JSON 的具体层级。
"""

from __future__ import annotations

import httpx  # 异步 HTTP 客户端，用于向外部 LLM 服务发送网络请求。
from pydantic import BaseModel  # 校验服务端返回的 JSON 结构。

from app.core.config import settings


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


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """发送聊天请求并返回第一个候选答案的文本。

    输入：按角色排列的消息列表，以及可选模型名和温度。
    输出：``choices[0].message.content`` 字符串。
    异常：配置缺失、HTTP 失败或响应格式不符时抛出 LLMClientError。
    """
    # 第一阶段：在网络请求前检查必要配置，尽早给出清晰错误。
    if not settings.llm_api_key:
        raise LLMClientError("缺少 LLM_API_KEY，请在 .env 中配置。")

    # 第二阶段：按照服务端协议组装 URL、JSON 请求体和认证请求头。
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

    # AsyncClient 的上下文管理器会在退出时自动释放连接资源。
    # await 期间当前协程暂停，但事件循环仍可处理其他 HTTP 请求。
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)

    # 第三阶段：把 4xx/5xx 状态转换成本项目统一异常。
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LLMClientError(
            f"LLM 请求失败：{response.status_code} {response.text}"
        ) from exc

    # 第四阶段：response.json() 解码 JSON，Pydantic 再检查所需嵌套字段。
    try:
        data = LLMChatResponse.model_validate(response.json())
    except (ValueError, TypeError) as exc:
        raise LLMClientError("LLM 返回格式异常") from exc

    if not data.choices:
        raise LLMClientError("LLM 返回中没有 choices")

    # 业务层只需要文本，因此隐藏外部 API 的 choices/message 包装结构。
    return data.choices[0].message.content
