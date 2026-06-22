"""只依据现有 CNKGraph 候选证据生成受控审阅与短注。"""

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


def _flatten_reviewable_evidence(
    candidate: AllusionCandidateEvidenceItem,
) -> list[dict[str, Any]]:
    """把实际返回给 Reader 的候选证据展平成带稳定 ID 的审阅输入。"""
    records: list[dict[str, Any]] = []
    for result in candidate.evidence_results:
        if result.status != "hit":
            continue
        for item in result.items:
            records.append(
                {
                    "evidence_id": f"e{len(records) + 1}",
                    "source": result.source,
                    "query_used": result.query_used,
                    "title": item.title,
                    "claim": item.claim,
                    "evidence_text": item.evidence_text,
                    "source_ref": item.source_ref,
                    "anchor_text": item.anchor_text,
                    "context_relation": item.context_relation,
                }
            )
    return records


def build_evidence_review_prompt(
    poem: PoemModel,
    candidate: AllusionCandidateEvidenceItem,
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """构造不允许检索、补记忆或自由赏析的 Reviewer 提示词。"""
    system_prompt = (
        "你是宋词候选证据审阅器，不是自由赏析者。"
        "你只能审阅输入中已经存在的 CNKGraph 候选证据。"
        "不得进行 Web 搜索，不得凭记忆补充出处、书名、人物或故事。"
        "必须区分事实证据与解释性推断；证据不足时明确返回 insufficient_evidence。"
        "输出严格 JSON，不要输出 Markdown 或额外说明。"
    )
    user_prompt = f"""
请审阅下面一个典故/化用候选的已有证据。

当前作品：{poem.dynasty} {poem.author}《{poem.tune_name}{('·' + poem.title) if poem.title else ''}》
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
9. “燕台句”若只有黄金台或其他宽泛弱命中，不得解释成黄金台，应返回 insufficient_evidence 或 ambiguous。
10. “南都石黛”若现有证据明确含徐陵《玉台新咏序》及石黛/眉喻信息，可以生成谨慎短注；不得扩写知人论世。
11. “前度刘郎”应优先刘禹锡、玄都观相关前代证据，当前周邦彦作品自命中降级。
12. “事与孤鸿去”若已有杜牧原诗证据，可标为 prior_source；当前周邦彦作品自命中降级。
""".strip()
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _insufficient_review(caveat: str) -> EvidenceReviewResult:
    return EvidenceReviewResult(
        review_status="insufficient_evidence",
        confidence="low",
        short_note=None,
        caveat=caveat,
    )


def _sanitize_review_item(
    raw: Any,
    evidence_by_id: dict[str, dict[str, Any]],
) -> EvidenceItemReview | None:
    """只接受确实指向输入证据的 Reviewer 条目，并覆盖确定性时间关系。"""
    try:
        reviewed = EvidenceItemReview.model_validate(raw)
    except ValidationError:
        return None
    source = evidence_by_id.get(reviewed.evidence_id)
    if source is None:
        return None
    if (
        reviewed.source != source["source"]
        or reviewed.query_used != source["query_used"]
        or reviewed.title != source["title"]
    ):
        return None

    forced_role = {
        "prior_source": "prior_source",
        "current_poem": "current_work_self_hit",
        "later_usage": "later_reuse",
    }.get(source.get("context_relation"))
    return reviewed.model_copy(
        update={
            "source_ref": source.get("source_ref"),
            "role": forced_role or reviewed.role,
        }
    )


def normalize_evidence_review(
    payload: Any,
    evidence: list[dict[str, Any]],
) -> EvidenceReviewResult:
    """过滤虚构引用，并强制自命中/后代用例降级及无证据不出短注。"""
    if not isinstance(payload, dict):
        raise ValueError("Reviewer 返回结果不是对象")
    evidence_by_id = {item["evidence_id"]: item for item in evidence}

    accepted: dict[str, list[EvidenceItemReview]] = {
        "best_evidence": [],
        "downgraded_evidence": [],
        "rejected_evidence": [],
    }
    seen: set[str] = set()
    for group_name in accepted:
        raw_group = payload.get(group_name, [])
        if not isinstance(raw_group, list):
            continue
        for raw in raw_group:
            item = _sanitize_review_item(raw, evidence_by_id)
            if item is None or item.evidence_id in seen:
                continue
            seen.add(item.evidence_id)
            target_group = group_name
            if item.role in {"current_work_self_hit", "later_reuse", "weak_related", "unknown"}:
                target_group = "downgraded_evidence"
            if item.role == "irrelevant" or item.relevance == "none":
                target_group = "rejected_evidence"
            if target_group == "best_evidence" and not (
                item.role == "prior_source" and item.relevance in {"strong", "medium"}
            ):
                target_group = "downgraded_evidence"
            accepted[target_group].append(item)

    # Reviewer 可能遗漏自命中等条目；补入 unknown 组，避免它们无声消失。
    for evidence_id, source in evidence_by_id.items():
        if evidence_id in seen:
            continue
        relation = source.get("context_relation")
        role = {
            "prior_source": "prior_source",
            "current_poem": "current_work_self_hit",
            "later_usage": "later_reuse",
        }.get(relation, "unknown")
        item = EvidenceItemReview(
            evidence_id=evidence_id,
            source=source["source"],
            query_used=source["query_used"],
            title=source.get("title"),
            source_ref=source.get("source_ref"),
            role=role,
            relevance="weak",
            reason="Reviewer 未将该候选证据列为最佳证据。",
        )
        accepted["downgraded_evidence"].append(item)

    best = accepted["best_evidence"]
    short_note = str(payload.get("short_note") or "").strip() or None
    if not best or not short_note:
        has_plausible = any(
            item.relevance in {"strong", "medium"}
            for item in accepted["downgraded_evidence"]
        )
        return EvidenceReviewResult(
            review_status="ambiguous" if has_plausible else "insufficient_evidence",
            confidence="low",
            short_note=None,
            best_evidence=[],
            downgraded_evidence=accepted["downgraded_evidence"],
            rejected_evidence=accepted["rejected_evidence"],
            caveat=str(payload.get("caveat") or "现有候选证据不足以生成可靠短注。")[:240],
        )

    confidence = payload.get("confidence")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return EvidenceReviewResult(
        review_status="reviewed",
        confidence=confidence,
        short_note=short_note[:240],
        best_evidence=best,
        downgraded_evidence=accepted["downgraded_evidence"],
        rejected_evidence=accepted["rejected_evidence"],
        caveat=(str(payload.get("caveat"))[:240] if payload.get("caveat") else None),
    )


async def review_allusion_candidate(
    poem: PoemModel,
    candidate: AllusionCandidateEvidenceItem,
) -> EvidenceReviewResult:
    """调用 LLM 审阅单个候选；没有可展示证据时不调用模型。"""
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


async def build_allusion_evidence_review(
    poem: PoemModel,
) -> AllusionCandidateReviewResponse:
    """复用候选证据预览，并逐候选隔离 Reviewer 错误。"""
    preview = await build_allusion_evidence_preview(poem)
    items: list[AllusionCandidateReviewedItem] = []
    errors = list(preview.errors)

    for candidate in preview.items:
        try:
            review = await review_allusion_candidate(poem, candidate)
        except Exception as exc:
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
