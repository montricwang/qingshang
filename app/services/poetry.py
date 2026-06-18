"""自由文本赏析的提示词组装服务。"""

from app.services.llm_client import chat_completion


async def explain_poetry(text: str, focus: str | None = None) -> str:
    """根据文本和可选关注点请求 LLM 生成自然语言赏析。

    输入：词句正文 ``text`` 和可选赏析重点 ``focus``。
    输出：LLM 返回的自然语言字符串。
    """
    # 有 focus 就把用户关注点明确写入提示词，否则采用默认分析维度。
    focus_instruction = (
        f"赏析重点：{focus}" if focus else "赏析重点：整体意境、情感、语言风格"
    )
    # system 消息规定助手身份和回答边界，user 消息携带本次具体任务。
    messages = [
        {
            "role": "system",
            "content": (
                "你是清商项目中的宋词赏析助手。"
                "你的回答应当准确、克制、有文学感，避免空泛套话。"
                "如果用户只给出一句词，就围绕这一句解释；"
                "如果用户给出一段词，就结合上下文赏析。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"请赏析下面这段词句：\n\n{text}\n\n"
                f"{focus_instruction}\n\n"
                "请用自然段回答，不要写成项目符号列表。"
            ),
        },
    ]

    # 具体网络协议由 llm_client 处理，本服务只负责文学业务提示词。
    return await chat_completion(messages=messages, temperature=0.6)
