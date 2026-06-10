from app.services.deepseek import chat_completion


async def explain_poetry(text: str, focus: str | None = None) -> str:
    focus_instruction = (
        f"赏析重点：{focus}" if focus else "赏析重点：整体意境、情感、语言风格"
    )
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

    return await chat_completion(messages=messages, temperature=0.6)
