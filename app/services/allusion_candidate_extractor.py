"""使用 LLM 从整首词中提取值得进一步查证的典故候选。"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from app.models.poem import PoemModel
from app.schemas.allusion import AllusionCandidateItem, AllusionCandidateResponse
from app.services.llm_client import chat_completion
from app.services.poem_analyzer import build_poem_text_for_prompt, extract_json


REASON_TEMPLATES = {
    "allusion": "该原文短语具有用事或典故化表达的可能，值得进一步查证。",
    "literary_reference": "该原文短语可能涉及前代文献或文学语句的化用，值得进一步查证。",
    "historical_place": "该地名可能承载超出字面地点的历史文化语境，值得进一步查证。",
    "cultural_institution": "该原文短语可能涉及节令、礼俗、制度或文化名物，值得进一步查证。",
    "conventional_motif": "该原文短语可能关联固定的文学表达传统，值得进一步查证。",
    "uncertain": "该原文短语疑似具有字面意义之外的文化关联，但目前无法确定，值得进一步查证。",
}


def build_allusion_candidate_prompt(poem: PoemModel) -> list[dict[str, str]]:
    """生成只识别疑似典故、不负责解释出处的严格提示词。"""
    poem_text = build_poem_text_for_prompt(poem)
    system_prompt = (
        "你是宋词阅读中的典故候选识别器。"
        "只寻找疑似典故、用事、文献化用、历史地名、节令制度和固定文学传统。"
        "不要识别普通意象、主题词、佳句、情感表达或结构焦点。"
        "不要解释典故，不要编造出处、书名、人物故事或历史事实。"
        "你只能说明某段原文为什么值得进一步检索。"
        "请输出严格 JSON，不要输出 Markdown 或额外说明。"
    )
    user_prompt = f"""
请识别下面整首词中值得进一步查证的典故候选。

作者：{poem.author}
词牌：{poem.tune_name}
题名：{poem.title or "无"}
题序：{poem.preface or "无"}

原文分句如下：
{poem_text}

请严格按照下面结构输出：

{{
  "candidates": [
    {{
      "line_no": 1,
      "anchor_text": "逐字复制自对应原句的短语",
      "candidate_type": "allusion",
      "query": "适合后续检索的简短关键词",
      "reason": "只说明为什么疑似值得查，不给出未经证实的出处或故事",
      "confidence": "high"
    }}
  ]
}}

candidate_type 只能是：
- allusion：较明确的典故或用事
- literary_reference：疑似文献语句或前人作品化用
- historical_place：带历史文化指向的地名
- cultural_institution：节令、礼俗、制度或文化名物
- conventional_motif：有固定文学传统的表达，例如折柳送别
- uncertain：确实值得查证但暂不能归类

要求：
1. anchor_text 必须逐字存在于对应 line_no 的原句中，不得改写。
2. 全词最多 10 个候选，每句最多 2 个候选。
3. 普通花鸟风月、一般景物、主题词、抒情身份、漂亮句子和篇章结构不要输出。
4. 只有在它关联固定文学传统时才输出普通词语，并在 reason 中明确说明需查证的传统。
5. 不确定时宁可省略；不得为了凑数量而输出。
6. 不得声称候选出自某书、某诗或某人物故事；本步骤不做出处确认。
7. 若没有候选，返回 {{"candidates": []}}。
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def filter_allusion_candidates(
    raw_candidates: Any,
    poem: PoemModel,
) -> list[AllusionCandidateItem]:
    """过滤结构错误、定位错误及超过句级或全词上限的模型输出。"""
    if not isinstance(raw_candidates, list):
        raise ValueError("模型返回的 candidates 不是数组")

    line_text_by_no = {
        line.global_line_no: line.text
        for section in poem.sections
        for line in section.lines
    }
    counts_by_line: dict[int, int] = defaultdict(int)
    accepted: list[AllusionCandidateItem] = []
    seen: set[tuple[int, str]] = set()

    for raw_candidate in raw_candidates:
        try:
            candidate = AllusionCandidateItem.model_validate(raw_candidate)
        except ValidationError:
            continue

        # reason 只保留分类层面的“为何值得查”。模型提出的具体出处或人物故事
        # 尚未经过证据工具核验，不能直接进入 API 响应。
        candidate = candidate.model_copy(
            update={"reason": REASON_TEMPLATES[candidate.candidate_type]}
        )

        source_line = line_text_by_no.get(candidate.line_no)
        candidate_key = (candidate.line_no, candidate.anchor_text)
        if (
            not source_line
            or candidate.anchor_text not in source_line
            or counts_by_line[candidate.line_no] >= 2
            or candidate_key in seen
        ):
            continue

        accepted.append(candidate)
        counts_by_line[candidate.line_no] += 1
        seen.add(candidate_key)
        if len(accepted) >= 10:
            break

    return accepted


async def extract_allusion_candidates(poem: PoemModel) -> AllusionCandidateResponse:
    """请求 LLM，并返回经过本地原文定位和数量约束的候选。"""
    raw_text = await chat_completion(
        messages=build_allusion_candidate_prompt(poem),
        temperature=0.1,
    )
    try:
        payload = json.loads(extract_json(raw_text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型没有返回合法 JSON：{raw_text}") from exc
    if not isinstance(payload, dict) or "candidates" not in payload:
        raise ValueError("模型返回中缺少 candidates")

    candidates = filter_allusion_candidates(payload["candidates"], poem)
    return AllusionCandidateResponse(poem_id=poem.poem_id, candidates=candidates)
