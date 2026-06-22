"""为 LLM 识别的典故候选自动查询现有 CNKGraph 证据。"""

from __future__ import annotations

from collections.abc import Awaitable

from app.models.poem import PoemModel
from app.schemas.allusion import (
    AllusionCandidateEvidenceItem,
    AllusionCandidateEvidenceResponse,
    CandidateEvidenceResult,
    EvidenceSource,
)
from app.schemas.cnkgraph import AllusionCandidate, EvidenceItem
from app.services.allusion_candidate_extractor import extract_allusion_candidates
from app.services.cnkgraph_client import CNKGraphClientError
from app.services.cnkgraph_tools import (
    build_allusion_candidates,
    build_reference_evidences,
)

MAX_QUERIES_PER_CANDIDATE = 3
MAX_DISPLAYED_PER_RESULT = 3


def _allusion_as_evidence(item: AllusionCandidate) -> EvidenceItem:
    """把典故候选转换为证据预览共用的窄字段，并丢弃 raw。"""
    return EvidenceItem(
        source="cnkgraph",
        tool_name="allusion",
        anchor_text=item.keyword,
        title=item.title,
        claim=item.explanation,
        evidence_text=item.source_text,
        source_ref=item.source_ref,
        match_status="candidate",
        raw=None,
    )


def _without_raw(item: EvidenceItem) -> EvidenceItem:
    """证据预览只返回清商字段，不向 Reader 透传第三方原始结构。"""
    return item.model_copy(update={"raw": None})


def _evidence_key(item: EvidenceItem) -> tuple[str, str, str]:
    """以标题、来源和证据文本标识同一来源下的重复结果。"""
    return (
        item.title or "",
        item.source_ref or "",
        item.evidence_text or item.claim or item.anchor_text or "",
    )


async def _collect_evidence_result(
    *,
    source: EvidenceSource,
    query: str,
    operation: Awaitable[list[EvidenceItem] | list[AllusionCandidate]],
    seen: set[tuple[str, str, str]],
) -> CandidateEvidenceResult:
    """执行一个 query/source，并把 404、空结果和局部错误稳定分类。"""
    try:
        raw_items = await operation
    except CNKGraphClientError as exc:
        if exc.status_code == 404:
            return CandidateEvidenceResult(
                source=source,
                query_used=query,
                status="no_result",
            )
        return CandidateEvidenceResult(
            source=source,
            query_used=query,
            status="error",
            error=str(exc),
        )

    if source == "cnkgraph_allusion":
        items = [_allusion_as_evidence(item) for item in raw_items]
    else:
        items = [_without_raw(item) for item in raw_items]

    unique_items: list[EvidenceItem] = []
    for item in items:
        key = _evidence_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)

    hit_count = len(items)
    displayed = unique_items[:MAX_DISPLAYED_PER_RESULT]
    if hit_count == 0:
        status = "no_result"
    else:
        status = "hit"
    return CandidateEvidenceResult(
        source=source,
        query_used=query,
        status=status,
        hit_count=hit_count,
        displayed_count=len(displayed),
        truncated=hit_count > len(displayed),
        items=displayed,
    )


def _overall_status(results: list[CandidateEvidenceResult]) -> str:
    statuses = {result.status for result in results}
    if "hit" in statuses and "error" in statuses:
        return "partial_error"
    if "hit" in statuses:
        return "hit"
    if statuses == {"error"}:
        return "error"
    if "error" in statuses:
        return "partial_error"
    return "no_result"


async def build_allusion_evidence_preview(
    poem: PoemModel,
) -> AllusionCandidateEvidenceResponse:
    """识别整首词候选，并为每个查询变体生成可独立降级的证据结果。"""
    extracted = await extract_allusion_candidates(poem)
    preview_items: list[AllusionCandidateEvidenceItem] = []
    errors: list[str] = []

    for candidate in extracted.candidates[:10]:
        evidence_results: list[CandidateEvidenceResult] = []
        seen_by_source: dict[EvidenceSource, set[tuple[str, str, str]]] = {
            "cnkgraph_allusion": set(),
            "cnkgraph_reference": set(),
        }
        for query in candidate.query_variants[:MAX_QUERIES_PER_CANDIDATE]:
            allusion_result = await _collect_evidence_result(
                source="cnkgraph_allusion",
                query=query,
                operation=build_allusion_candidates(query),
                seen=seen_by_source["cnkgraph_allusion"],
            )
            reference_result = await _collect_evidence_result(
                source="cnkgraph_reference",
                query=query,
                operation=build_reference_evidences(query),
                seen=seen_by_source["cnkgraph_reference"],
            )
            evidence_results.extend((allusion_result, reference_result))

        for result in evidence_results:
            if result.status == "error" and result.error:
                errors.append(
                    f"{candidate.anchor_text} / {result.source} / "
                    f"{result.query_used}: {result.error}"
                )

        preview_items.append(
            AllusionCandidateEvidenceItem(
                **candidate.model_dump(),
                evidence_results=evidence_results,
                overall_status=_overall_status(evidence_results),
            )
        )

    return AllusionCandidateEvidenceResponse(
        poem_id=poem.poem_id,
        items=preview_items,
        errors=errors,
    )
