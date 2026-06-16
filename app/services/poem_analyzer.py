from __future__ import annotations

import json
import re

from app.models.poem import PoemModel
from app.schemas.analysis import PoemAnalysis
from app.services.llm_client import chat_completion


def build_poem_text_for_prompt(poem: PoemModel) -> str:
    sections = sorted(poem.sections, key=lambda section: section.section_no)

    blocks: list[str] = []

    for section in sections:
        section_name = section.section_name or "正文"
        lines = sorted(section.lines, key=lambda line: line.global_line_no)

        block_lines = [f"【{section_name}】"]

        for line in lines:
            block_lines.append(
                f"{line.global_line_no}. "
                f"({section_name}第{line.section_line_no}句) "
                f"{line.text}"
            )

        blocks.append("\n".join(block_lines))

    return "\n\n".join(blocks)


def extract_json(text: str) -> str:
    """
    兼容模型返回 ```json ... ``` 的情况。
    """
    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        return fenced.group(1).strip()

    return text


def build_analysis_prompt(poem: PoemModel) -> list[dict[str, str]]:
    poem_text = build_poem_text_for_prompt(poem)

    title_part = f"《{poem.tune_name}"
    if poem.title:
        title_part += f"·{poem.title}"
    title_part += "》"

    preface_part = poem.preface or "无"

    system_prompt = (
        "你是一名宋词赏析助手。"
        "你的任务是基于给定原文做解释，不要编造作者生平、写作背景或不存在的典故。"
        "请输出严格 JSON，不要输出 Markdown，不要添加额外说明。"
    )

    user_prompt = f"""
请分析下面这首宋词。

作者：{poem.author}
词牌：{poem.tune_name}
宫调：{poem.musical_mode or "无"}
题名：{poem.title or "无"}
题序：{preface_part}

原文分句如下：
{poem_text}

请严格按照下面 JSON 结构输出：

{{
  "poem_id": "{poem.poem_id}",
  "tune_name": "{poem.tune_name}",
  "title": {json.dumps(poem.title, ensure_ascii=False)},
  "summary": "整首词的大意，控制在 150 字以内",
  "emotional_flow": "说明情感如何推进，控制在 150 字以内",
  "style": "说明语言风格和艺术特点，控制在 150 字以内",
  "imagery": [
    {{
      "image": "意象名称",
      "meaning": "这个意象在词中的作用"
    }}
  ],
  "line_explanations": [
    {{
      "global_line_no": 1,
      "section_name": "上片",
      "section_line_no": 1,
      "original": "原句",
      "translation": "白话翻译",
      "explanation": "简要赏析"
    }}
  ]
}}

要求：
1. line_explanations 必须覆盖每一个原文分句。
2. global_line_no、section_line_no 必须和原文编号一致。
3. original 必须逐字复制原句，不要改写。
4. translation 用现代汉语解释句意。
5. explanation 说明这一句的情感、意象、语气或结构作用。
6. 如果不确定典故，不要硬说。
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def analyze_poem(poem: PoemModel) -> PoemAnalysis:
    messages = build_analysis_prompt(poem)

    raw_text = await chat_completion(
        messages=messages,
        temperature=0.2,
    )

    json_text = extract_json(raw_text)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型没有返回合法 JSON：{raw_text}") from exc

    analysis = PoemAnalysis.model_validate(data)

    return analysis
