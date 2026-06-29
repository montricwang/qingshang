"""只依据现有 CNKGraph 候选证据生成受控审阅与短注。

数据流：
证据预览（AllusionCandidateEvidenceItem）
  → 展平证据为可审阅格式
  → 构造 Reviewer prompt
  → LLM 审阅
  → 校验模型输出（过滤虚构证据 ID、强制角色覆盖）
  → 汇总结论
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.models.poem import PoemModel
from app.schemas.allusion import (
    AllusionCandidateEvidenceItem,
    AllusionCandidateReviewResponse,
    AllusionCandidateReviewedItem,
    EvidenceItemReview,
    EvidenceReviewResult,
)
from app.services.allusion_evidence import build_allusion_evidence_preview
from app.services.llm_client import chat_completion
from app.services.poem_analyzer import extract_json


# ============================================================================
# 步骤 1：展平证据 → 构造审阅 prompt
# ============================================================================

def _flatten_reviewable_evidence(
    candidate: AllusionCandidateEvidenceItem,
) -> list[dict[str, Any]]:
    """把候选下所有来源的证据展平为带编号的 dict 列表，供 LLM 审阅。

    每个证据条目包含：evidence_id、来源、查询词、标题、主张、证据文本、来源信息。
    """
    records: list[dict[str, Any]] = []
    for result in candidate.evidence_results:
        if result.status != "hit":
            continue
        for item in result.items:
            records.append({
                "evidence_id": f"e{len(records) + 1}",
                "source": result.source,
                "query_used": result.query_used,
                "title": item.title,
                "claim": item.claim,
                "evidence_text": item.evidence_text,
                "source_ref": item.source_ref,
                "anchor_text": item.anchor_text,
                "context_relation": item.context_relation,
            })
    return records


def _reviewer_system_prompt() -> str:
    return (
        "你是宋词候选证据审阅器，不是自由赏析者。"
        "你只能审阅输入中已经存在的 CNKGraph 候选证据。"
        "不得进行 Web 搜索，不得凭记忆补充出处、书名、人物或故事。"
        "必须区分事实证据与解释性推断；证据不足时明确返回 insufficient_evidence。"
        "输出严格 JSON，不要输出 Markdown 或额外说明。"
    )


def _reviewer_user_prompt(
    poem: PoemModel,
    candidate: AllusionCandidateEvidenceItem,
    evidence: list[dict[str, Any]],
) -> str:
    title_part = f"{poem.dynasty} {poem.author}《{poem.tune_name}"
    if poem.title:
        title_part += f"·{poem.title}"
    title_part += "》"

    return f"""
请审阅下面一个典故/化用候选的已有证据。

当前作品：{title_part}
原句：{candidate.line_text}
候选锚点：{candidate.anchor_text}
候选类型：{candidate.candidate_type}
候选理由：{candidate.reason}

已有候选证据：
{json.dumps(evidence, ensure_ascii=False, indent=2)}

请输出：
{{
  "review_status": "reviewed",
  "confidence": "high",
  "short_note": "只基于最佳证据的一至两句审阅短注",
  "best_evidence": [
    {{
      "evidence_id": "e1",
      "source": "cnkgraph_reference",
      "query_used": "查询词",
      "title": "证据标题或 null",
      "source_ref": "来源或 null",
      "role": "prior_source",
      "relevance": "strong",
      "reason": "只说明这条现有证据为何贴合"
    }}
  ],
  "downgraded_evidence": [],
  "rejected_evidence": [],
  "caveat": null
}}

review_status 只能是 reviewed / insufficient_evidence / ambiguous。
role 只能是 prior_source / current_work_self_hit / later_reuse / weak_related / irrelevant / unknown。
relevance 只能是 strong / medium / weak / none。

规则：
1. 只能引用上方已有 evidence_id；source、query_used、title 必须与该条证据一致。
2. context_relation=current_poem 必须标为 current_work_self_hit，不能进入 best_evidence。
3. context_relation=later_usage 必须标为 later_reuse，只能作为流传或再用参考。
4. context_relation=prior_source 可优先标为 prior_source；前代来源优先于后代沿用。
5. 典故词条解释通常比当前作品自命中更有解释价值，但仍需判断是否贴合原文锚点。
6. 弱相关、同词异义和宽泛 query 的误命中必须降级或拒绝。
7. short_note 只能依据 best_evidence，限一至两句；不得引入证据中没有的书名、人物或故事。
8. 没有 strong/medium 的前代来源时，short_note 必须为 null，返回 insufficient_evidence 或 ambiguous。
9. "燕台句"若只有黄金台或其他宽泛弱命中，不得解释成黄金台，应返回 insufficient_evidence 或 ambiguous。
10. "南都石黛"若现有证据明确含徐陵《玉台新咏序》及石黛/眉喻信息，可以生成谨慎短注；不得扩写知人论世。
11. "前度刘郎"应优先刘禹锡、玄都观相关前代证据，当前周邦彦作品自命中降级。
12. "事与孤鸿去"若已有杜牧原诗证据，可标为 prior_source；当前周邦彦作品自命中降级。
""".strip()


def build_evidence_review_prompt(
    poem: PoemModel,
    candidate: AllusionCandidateEvidenceItem,
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """构造不允许检索、补记忆或自由赏析的 Reviewer 提示词。"""
    return [
        {"role": "system", "content": _reviewer_system_prompt()},
        {"role": "user", "content": _reviewer_user_prompt(poem, candidate, evidence)},
    ]


# ============================================================================
# 步骤 2：解析 + 校验 LLM 审阅结果
# ============================================================================

def _insufficient_review(caveat: str) -> EvidenceReviewResult:
    """快速生成一个"证据不足"的审阅结果。"""
    return EvidenceReviewResult(
        review_status="insufficient_evidence",
        confidence="low",
        short_note=None,
        caveat=caveat,
    )


def _validate_review_item(
    raw: Any,
    evidence_by_id: dict[str, dict[str, Any]],
) -> EvidenceItemReview | None:
    """校验 LLM 输出的一条审阅条目是否引用了真实存在的输入证据。

    返回 None 的情况：
    - JSON 结构不符合 EvidenceItemReview 的 Pydantic 模型
    - 引用的 evidence_id 不存在于输入证据中
    - source / query_used / title 与输入不匹配（模型虚构了引用）
    """
    try:
        reviewed = EvidenceItemReview.model_validate(raw)
    except ValidationError:
        return None

    source = evidence_by_id.get(reviewed.evidence_id)
    if source is None:
        return None

    # 确保模型没有篡改证据的关键字段
    if (
        reviewed.source != source["source"]
        or reviewed.query_used != source["query_used"]
        or reviewed.title != source["title"]
    ):
        return None

    # 根据 context_relation 强制覆盖 role，防止模型把当前作品自引用说成前代来源
    forced_role = _force_role_from_context(source.get("context_relation"))
    return reviewed.model_copy(update={
        "source_ref": source.get("source_ref"),
        "role": forced_role or reviewed.role,
    })


def _force_role_from_context(context_relation: str | None) -> str | None:
    """把 context_relation 的原始值映射到强制 role。

    这些是程序已知的确定性关系，不允许 Reviewer 覆盖：
    - prior_source → prior_source（前代来源，模型可正常使用）
    - current_poem → current_work_self_hit（当前作品自引用，必须识别）
    - later_usage  → later_reuse（后代用例，不应作为最佳证据）
    """
    mapping = {
        "prior_source": "prior_source",
        "current_poem": "current_work_self_hit",
        "later_usage": "later_reuse",
    }
    return mapping.get(context_relation) if context_relation else None


# ============================================================================
# 步骤 3：分类、补漏、最终裁决
# ============================================================================

def _classify_reviewed_items(
    payload: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> tuple[list[EvidenceItemReview], list[EvidenceItemReview], list[EvidenceItemReview], set[str]]:
    """把 LLM 审阅结果按 best / downgraded / rejected 三组分类。

    返回：(best, downgraded, rejected, 已处理过的 evidence_id 集合)
    """
    best: list[EvidenceItemReview] = []
    downgraded: list[EvidenceItemReview] = []
    rejected: list[EvidenceItemReview] = []
    seen: set[str] = set()

    # 模型输出分三组：best_evidence / downgraded_evidence / rejected_evidence
    groups = [
        ("best_evidence", best),
        ("downgraded_evidence", downgraded),
        ("rejected_evidence", rejected),
    ]

    for group_name, target_list in groups:
        raw_group = payload.get(group_name, [])
        if not isinstance(raw_group, list):
            continue
        for raw in raw_group:
            item = _validate_review_item(raw, evidence_by_id)
            if item is None or item.evidence_id in seen:
                continue
            seen.add(item.evidence_id)

            # 以下角色即使模型放在 best_evidence 也要强制降级或拒绝
            if item.role in {"current_work_self_hit", "later_reuse", "weak_related", "unknown"}:
                downgraded.append(item)
            elif item.role == "irrelevant" or item.relevance == "none":
                rejected.append(item)
            elif item.role == "prior_source" and item.relevance in {"strong", "medium"}:
                # 这才是合格的最佳证据
                best.append(item)
            else:
                downgraded.append(item)

    return best, downgraded, rejected, seen


def _add_unreviewed_evidence(
    evidence_by_id: dict[str, dict[str, Any]],
    seen: set[str],
    downgraded: list[EvidenceItemReview],
) -> None:
    """把 Reviewer 漏掉的证据条目补入降级组，不让他们无声消失。"""
    for evidence_id, source in evidence_by_id.items():
        if evidence_id in seen:
            continue
        relation = source.get("context_relation")
        role = {
            "prior_source": "prior_source",
            "current_poem": "current_work_self_hit",
            "later_usage": "later_reuse",
        }.get(relation, "unknown")

        downgraded.append(EvidenceItemReview(
            evidence_id=evidence_id,
            source=source["source"],
            query_used=source["query_used"],
            title=source.get("title"),
            source_ref=source.get("source_ref"),
            role=role,
            relevance="weak",
            reason="Reviewer 未将该候选证据列为最佳证据。",
        ))


def _determine_final_status(
    best: list[EvidenceItemReview],
    downgraded: list[EvidenceItemReview],
    rejected: list[EvidenceItemReview],
    payload: dict[str, Any],
) -> EvidenceReviewResult:
    """基于 best_evidence 是否存在来决定最终审阅状态。

    - 有 best_evidence 且有 short_note → reviewed
    - 无 best_evidence 但有 plausible 条目 → ambiguous
    - 无任何有解释价值的证据 → insufficient_evidence
    """
    short_note = str(payload.get("short_note") or "").strip() or None

    if best and short_note:
        # 有合格的最佳证据 + 审阅短注
        confidence = payload.get("confidence")
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        return EvidenceReviewResult(
            review_status="reviewed",
            confidence=confidence,
            short_note=short_note[:240],
            best_evidence=best,
            downgraded_evidence=downgraded,
            rejected_evidence=rejected,
            caveat=(str(payload.get("caveat"))[:240] if payload.get("caveat") else None),
        )

    # 无 best_evidence：判断是 ambiguous 还是 insufficient
    has_plausible = any(
        item.relevance in {"strong", "medium"}
        for item in downgraded
    )
    return EvidenceReviewResult(
        review_status="ambiguous" if has_plausible else "insufficient_evidence",
        confidence="low",
        short_note=None,
        best_evidence=[],
        downgraded_evidence=downgraded,
        rejected_evidence=rejected,
        caveat=str(payload.get("caveat") or "现有候选证据不足以生成可靠短注。")[:240],
    )


def normalize_evidence_review(
    payload: Any,
    evidence: list[dict[str, Any]],
) -> EvidenceReviewResult:
    """把 LLM 返回的审阅结果过滤、分类、补充为可信的最终结论。

    执行步骤：
    ① 校验 payload 是否为 dict，建立 evidence_id → 原始证据 的索引
    ② 解析 LLM 的输出，分类进 best / downgraded / rejected 三组
    ③ 三组分类时强制执行角色覆盖和相关性降级
    ④ 把 Reviewer 遗漏的条目补入降级组
    ⑤ 基于 best_evidence 是否存在决定最终 review_status
    """
    # 步骤 ①
    if not isinstance(payload, dict):
        raise ValueError("Reviewer 返回结果不是对象")

    evidence_by_id = {item["evidence_id"]: item for item in evidence}

    # 步骤 ②-③：校验并分类
    best, downgraded, rejected, seen = _classify_reviewed_items(payload, evidence_by_id)

    # 步骤 ④：补漏
    _add_unreviewed_evidence(evidence_by_id, seen, downgraded)

    # 步骤 ⑤：最终裁决
    return _determine_final_status(best, downgraded, rejected, payload)


# ============================================================================
# 步骤 4：逐候选调用 LLM 审阅
# ============================================================================

async def review_allusion_candidate(
    poem: PoemModel,
    candidate: AllusionCandidateEvidenceItem,
) -> EvidenceReviewResult:
    """调用 LLM 审阅单个候选的证据；没有可展示证据时不调用模型。

    数据流：
    candidate → 展平证据 → prompt → chat_completion() → normalize_evidence_review()
    """
    evidence = _flatten_reviewable_evidence(candidate)
    if not evidence:
        return _insufficient_review("CNKGraph 未返回可供审阅的候选证据。")

    raw_text = await chat_completion(
        messages=build_evidence_review_prompt(poem, candidate, evidence),
        temperature=0.0,
    )

    try:
        payload = json.loads(extract_json(raw_text))
    except json.JSONDecodeError as exc:
        raise ValueError("Reviewer 没有返回合法 JSON") from exc

    return normalize_evidence_review(payload, evidence)


# ============================================================================
# 主入口：为整首词生成证据审阅
# ============================================================================

async def build_allusion_evidence_review(
    poem: PoemModel,
) -> AllusionCandidateReviewResponse:
    """先做候选证据预览，再逐候选进行受控 LLM 审阅。

    单个候选审阅失败只写入局部错误，不中断其他候选的审阅。
    """
    # 步骤 ①：获取候选证据预览
    preview = await build_allusion_evidence_preview(poem)

    items: list[AllusionCandidateReviewedItem] = []
    errors = list(preview.errors)

    # 步骤 ②：逐候选审阅
    for candidate in preview.items:
        try:
            review = await review_allusion_candidate(poem, candidate)
        except Exception as exc:
            # 单个候选失败不影响其他候选
            message = f"{candidate.anchor_text}: Evidence Review 失败"
            errors.append(message)
            review = EvidenceReviewResult(
                review_status="error",
                confidence="low",
                short_note=None,
                caveat=f"{message}；其他候选不受影响。",
            )

        items.append(
            AllusionCandidateReviewedItem(
                **candidate.model_dump(),
                review_result=review,
            )
        )

    return AllusionCandidateReviewResponse(
        poem_id=poem.poem_id,
        items=items,
        errors=errors,
    )
