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

# ---------------------------------------------------------------------------
# 候选理由模板：每种类型对应一句固定的谨慎说明。
# 模型可能输出未经核验的书名或人物故事，这里统一覆盖为"为何值得查"。
# ---------------------------------------------------------------------------
REASON_TEMPLATES = {
    "allusion": "该原文短语具有用事或典故化表达的可能，值得进一步查证。",
    "literary_reference": "该原文短语可能涉及前代文献语词、成句或诗文化用，值得进一步查证。",
    "historical_place": "该地名或地点表达可能承载历史、文学或游冶空间语境，值得进一步查证。",
    "cultural_institution": "该短语可能涉及节令、礼俗、制度或名物知识，值得进一步查证。",
    "conventional_motif": "该表达可能属于固定文学母题或惯用传统，值得进一步查证。",
    "uncertain": "该短语存在非字面解释的可能，但类型尚不明确，需进一步查证。",
}


# ============================================================================
# prompt 文本
# ============================================================================

def _allusion_candidate_system_prompt() -> str:
    return (
        "你是宋词阅读中的典故候选识别器。"
        "只寻找疑似典故、用事、文献化用、历史地名、节令制度和固定文学传统。"
        "不要识别普通意象、主题词、佳句、情感表达或结构焦点。"
        "这不是意象识别、赏析或主题词提取任务。"
        "不要解释典故，不要编造出处、书名、人物故事或历史事实。"
        "你只能说明某段原文为什么值得进一步检索。"
        "请输出严格 JSON，不要输出 Markdown 或额外说明。"
    )


def _allusion_examples() -> str:
    """返回 prompt 中的正反例文本，说明什么是/不是可查单位。"""
    return """
完整可查单位正例：
- 原句：吟笺赋笔，犹记燕台句。
  anchor_text：燕台句
  query_variants：["燕台句", "燕台诗", "李商隐 燕台诗"]
  禁止输出：燕台
- 原句：梨花榆火催寒食。
  候选一 anchor_text：榆火
  query_variants：["榆火", "榆火 寒食", "清明 赐火"]
  候选二 anchor_text：寒食
- 原句：长亭路，年去岁来，应折柔条过千尺。
  anchor_text：折柔条
  query_variants：["折柔条", "折柳送别", "折柳"]
  禁止只输出：柔条
- 原句：前度刘郎今又来。
  anchor_text：前度刘郎
  query_variants：["前度刘郎", "刘禹锡 前度刘郎"]
  禁止只输出：刘郎

反例：
- 柳阴直：普通视觉起笔，不作为典故候选。
- 京华倦客：主题性表达，不作为典故候选。
- 斜阳冉冉春无极：佳句或评论焦点，不作为典故候选。
- 沉思前事：情绪收束，不作为典故候选。
""".strip()


def _allusion_candidate_user_prompt(poem: PoemModel) -> str:
    poem_text = build_poem_text_for_prompt(poem)
    return f"""
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
      "query_variants": ["原文锚点", "其他检索提示"],
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
7. anchor_text 必须是"完整可查单位"，即能够让检索系统找到正确语义的最短原文片段。
8. 如果相邻字会改变语义或避免常见误检，必须一起纳入 anchor_text；不能为了短而截断。
9. query_variants 最多 4 个，第一项优先使用 anchor_text；它们只是查询提示，不是证据或事实断言。
10. 若没有候选，返回 {{"candidates": []}}。
11. historical_place 只用于原文确实以地点或地名为可查单位的情况；
    像"南都石黛"这样整体更像前代文献语词的短语，应优先考虑 literary_reference，
    不要只因其中含地名就分类为 historical_place。

{_allusion_examples()}
""".strip()


def build_allusion_candidate_prompt(poem: PoemModel) -> list[dict[str, str]]:
    """生成只识别完整可查单位、不负责解释出处的严格提示词。"""
    return [
        {"role": "system", "content": _allusion_candidate_system_prompt()},
        {"role": "user", "content": _allusion_candidate_user_prompt(poem)},
    ]


# ============================================================================
# 候选过滤：把 LLM 的原始输出变成可信任的候选列表
# ============================================================================

def _build_line_index(poem: PoemModel) -> dict[int, str]:
    """建立「句子编号 → 原句文本」的快速查找表。"""
    return {
        line.global_line_no: line.text
        for section in poem.sections
        for line in section.lines
    }


def _try_parse_candidate(
    raw: Any, line_text_by_no: dict[int, str]
) -> AllusionCandidateItem | None:
    """尝试把一条 LLM 输出解析为有效候选。

    返回 None 的情况：
    - JSON 字段不符合 Pydantic 模型要求
    - anchor_text 在对应原句中找不到（模型输出了不在原文里的内容）
    """
    try:
        candidate = AllusionCandidateItem.model_validate(raw)
    except ValidationError:
        return None

    source_line = line_text_by_no.get(candidate.line_no)
    if not source_line or candidate.anchor_text not in source_line:
        return None

    # 覆盖模型可能编造的理由，换为对应类型的固定谨慎模板
    return candidate.model_copy(
        update={
            "line_text": source_line,
            "reason": REASON_TEMPLATES[candidate.candidate_type],
        }
    )


def _remove_truncated_anchors(candidates: list[AllusionCandidateItem]) -> list[AllusionCandidateItem]:
    """同句内差 1-2 个字的截断关系，只保留较完整的。

    例如"燕台"包含在"燕台句"中且差 2 字以内 → 移除"燕台"。
    较长的独立短语不会因此吞掉同一句的另一个独立候选。
    """
    result: list[AllusionCandidateItem] = []
    for c in candidates:
        has_more_specific = any(
            other.line_no == c.line_no
            and c.anchor_text != other.anchor_text
            and c.anchor_text in other.anchor_text
            and len(other.anchor_text) - len(c.anchor_text) <= 2
            for other in candidates
        )
        if not has_more_specific:
            result.append(c)
    return result


def _enforce_limits(
    candidates: list[AllusionCandidateItem],
    max_per_line: int = 2,
    max_total: int = 10,
) -> list[AllusionCandidateItem]:
    """每句最多 max_per_line 项，全词最多 max_total 项，并去除重复锚点。"""
    accepted: list[AllusionCandidateItem] = []
    line_counts: dict[int, int] = defaultdict(int)
    seen: set[tuple[int, str]] = set()

    for c in candidates:
        key = (c.line_no, c.anchor_text)
        if key in seen:
            continue
        if line_counts[c.line_no] >= max_per_line:
            continue

        seen.add(key)
        accepted.append(c)
        line_counts[c.line_no] += 1

        if len(accepted) >= max_total:
            break

    return accepted


def filter_allusion_candidates(
    raw_candidates: Any,
    poem: PoemModel,
) -> list[AllusionCandidateItem]:
    """把 LLM 返回的原始候选列表变成可信、有序、符合限制的候选。

    执行步骤：
    ① 逐条尝试解析为 Pydantic 模型，跳过不符合结构的条目
    ② 检查 anchor_text 是否真的出现在对应原句中，不存在则丢弃
    ③ 覆盖模型理由为对应类型的固定谨慎模板
    ④ 同句内存在差 1-2 字的截断关系时，只保留较完整的那一个
    ⑤ 每句上限 2 项，全词上限 10 项，去除重复锚点
    """
    if not isinstance(raw_candidates, list):
        raise ValueError("模型返回的 candidates 不是数组")

    line_text_by_no = _build_line_index(poem)

    # 步骤 ①-③：解析、定位、覆盖理由
    parsed = []
    for raw in raw_candidates:
        candidate = _try_parse_candidate(raw, line_text_by_no)
        if candidate is not None:
            parsed.append(candidate)

    # 步骤 ④：去除截断
    deduped = _remove_truncated_anchors(parsed)

    # 步骤 ⑤：上限约束
    return _enforce_limits(deduped)


# ============================================================================
# 主入口
# ============================================================================

async def extract_allusion_candidates(poem: PoemModel) -> AllusionCandidateResponse:
    """请求 LLM 识别候选，并返回经过本地原文定位和数量约束的结果。

    数据流：
    poem (ORM) → prompt → chat_completion() → JSON 解析 → filter_allusion_candidates()
    """
    raw_text = await chat_completion(
        messages=build_allusion_candidate_prompt(poem),
        temperature=0.1,
    )

    # 解析 LLM 返回的 JSON
    try:
        payload = json.loads(extract_json(raw_text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型没有返回合法 JSON：{raw_text}") from exc

    if not isinstance(payload, dict) or "candidates" not in payload:
        raise ValueError("模型返回中缺少 candidates")

    # 过滤并返回
    candidates = filter_allusion_candidates(payload["candidates"], poem)
    return AllusionCandidateResponse(poem_id=poem.poem_id, candidates=candidates)
