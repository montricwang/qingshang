"""为 LLM 识别的典故候选自动查询现有 CNKGraph 证据。

数据流：
候选列表 → 每个候选取最多 3 个查询变体 → 分别调用 CNKGraph 典故 + 出处工具
→ 按来源去重 → 标记作品时间关系 → 排序 → 返回证据预览
"""

from __future__ import annotations

from collections.abc import Awaitable

from app.models.poem import PoemModel
from app.schemas.allusion import (
    AllusionCandidateItem,
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

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_QUERIES_PER_CANDIDATE = 3       # 每个候选最多使用多少个查询变体
MAX_DISPLAYED_PER_RESULT = 3        # 每个 query/source 组合最多展示多少条
RESULT_STATUS_SORT_ORDER = {"hit": 0, "no_result": 1, "error": 2}

# ---------------------------------------------------------------------------
# 朝代排序（粗粒度，只用于区分前代 / 本朝 / 后代）
# ---------------------------------------------------------------------------

DYNASTY_ORDER = {
    "先秦": 1, "秦": 2, "汉": 3, "魏晋": 4, "南北朝": 5,
    "隋": 6, "唐": 7, "五代": 8, "宋": 9, "元": 10,
    "明": 11, "清": 12, "近现代": 13,
}


def _dynasty_rank(source_ref: str | None) -> int | None:
    """从清商窄来源字符串中识别常用朝代编号。"""
    if not source_ref:
        return None
    for dynasty, rank in DYNASTY_ORDER.items():
        if dynasty in source_ref:
            return rank
    return None


# ---------------------------------------------------------------------------
# 证据去重与格式转换
# ---------------------------------------------------------------------------

def _allusion_as_evidence(item: AllusionCandidate) -> EvidenceItem:
    """把 CNKGraph 典故候选转为 EvidenceItem 窄字段。"""
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


def _strip_raw(item: EvidenceItem) -> EvidenceItem:
    """移除 CNKGraph 原始字段，只保留清商定义的窄字段。"""
    return item.model_copy(update={"raw": None})


def _evidence_key(item: EvidenceItem) -> tuple[str, str, str]:
    """用标题 + 来源 + 正文标识同一来源下的重复结果。"""
    return (
        item.title or "",
        item.source_ref or "",
        item.evidence_text or item.claim or item.anchor_text or "",
    )


# ---------------------------------------------------------------------------
# 作品时间关系标记
# ---------------------------------------------------------------------------

def _normalize_text(value: str | None) -> str:
    """移除空白和常见标点，只用于保守比较作品文本是否匹配。"""
    if not value:
        return ""
    return "".join(
        char for char in value if not char.isspace() and char not in "，。！？；、："
    )


def _is_from_current_poem(
    item: EvidenceItem,
    poem: PoemModel,
    current_line_text: str,
) -> bool:
    """判断这条证据是否来自当前作品本身。

    检查两项：① 来源文本引用了当前作品的作者+词牌/题名
              ② 或证据文本与当前句高度重合
    """
    source_ref = item.source_ref or ""

    # 检查 1：作者 + 词牌/题名 是否出现在来源文本中
    has_author_and_title = poem.author in source_ref and any(
        value and value in source_ref
        for value in (poem.title, poem.tune_name)
    )

    # 检查 2：证据文本是否与当前句一致或包含当前句
    ev_text = _normalize_text(item.evidence_text)
    line_text = _normalize_text(current_line_text)
    text_matches = bool(ev_text and line_text and (
        ev_text == line_text or ev_text in line_text
    ))

    return has_author_and_title or text_matches


def _determine_temporal_relation(
    item: EvidenceItem,
    poem: PoemModel,
) -> str | None:
    """根据证据来源的朝代表判断时间关系。

    返回 "prior_source" / "later_usage" / None（无法判断）。
    """
    source_rank = _dynasty_rank(item.source_ref)
    poem_rank = DYNASTY_ORDER.get(poem.dynasty)
    if source_rank is None or poem_rank is None:
        return None
    if source_rank < poem_rank:
        return "prior_source"
    if source_rank > poem_rank:
        return "later_usage"
    return None


def _context_relation(
    item: EvidenceItem,
    poem: PoemModel,
    current_line_text: str,
) -> str | None:
    """判断一条证据与当前作品的时间关系。

    优先级：
    ① 先检查是否是当前作品自引用（current_poem）
    ② 再根据朝代表判断前代来源或后代用例
    """
    if _is_from_current_poem(item, poem, current_line_text):
        return "current_poem"
    return _determine_temporal_relation(item, poem)


# ---------------------------------------------------------------------------
# 证据排序
# ---------------------------------------------------------------------------

# 数字越小越排前面
_RELATION_SORT_PRIORITY = {
    "prior_source": 0,   # 前代来源最优先
    None: 1,             # 未知时间关系
    "later_usage": 2,    # 后代用例往后
    "current_poem": 3,   # 当前作品自引用放最后
}


def _sort_by_quality(item: EvidenceItem) -> tuple[int, int]:
    """返回一个排序键：(时间关系优先级, 是否有摘要)。

    有来源的普通候选优先；当前作品和后代用例靠后。
    """
    relation_rank = _RELATION_SORT_PRIORITY.get(item.context_relation, 1)
    has_summary = bool(item.title and (item.claim or item.evidence_text or item.source_ref))
    return (relation_rank, 0 if has_summary else 1)


def _annotate_and_sort(
    items: list[EvidenceItem],
    poem: PoemModel,
    current_line_text: str,
) -> list[EvidenceItem]:
    """给每条证据标记时间关系，并按质量重新排序。"""
    annotated = [
        item.model_copy(
            update={"context_relation": _context_relation(item, poem, current_line_text)}
        )
        for item in items
    ]
    return sorted(annotated, key=_sort_by_quality)


# ---------------------------------------------------------------------------
# 一次查询的执行（典故 or 出处）
# ---------------------------------------------------------------------------

def _normalize_evidence_items(
    raw_items: list[EvidenceItem] | list[AllusionCandidate],
    source: EvidenceSource,
    seen: set[tuple[str, str, str]],
    poem: PoemModel,
    current_line_text: str,
) -> list[EvidenceItem]:
    """把 CNKGraph 原始条目转换为去重、标注时间关系并排序后的 EvidenceItem 列表。"""
    if source == "cnkgraph_allusion":
        items = [_allusion_as_evidence(item) for item in raw_items]
    else:
        items = [_strip_raw(item) for item in raw_items]

    unique_items: list[EvidenceItem] = []
    for item in items:
        key = _evidence_key(item)
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return _annotate_and_sort(unique_items, poem, current_line_text)


async def _collect_evidence_result(
    *,
    source: EvidenceSource,
    query: str,
    operation: Awaitable[list[EvidenceItem] | list[AllusionCandidate]],
    seen: set[tuple[str, str, str]],
    poem: PoemModel,
    current_line_text: str,
) -> CandidateEvidenceResult:
    """对某一个查询变体调用 CNKGraph 工具，返回去重并排序后的证据结果。

    失败时的行为：
    - 上游 404 → 标记为 no_result（正常，不是错误）
    - 其他网络/HTTP 错误 → 标记为 error，记录错误信息
    """
    try:
        raw_items = await operation
    except CNKGraphClientError as exc:
        if exc.status_code == 404:
            return CandidateEvidenceResult(
                source=source, query_used=query, status="no_result"
            )
        return CandidateEvidenceResult(
            source=source, query_used=query, status="error", error=str(exc)
        )

    unique_items = _normalize_evidence_items(
        raw_items, source, seen, poem, current_line_text
    )

    hit_count = len(raw_items) if isinstance(raw_items, list) else 0
    displayed = unique_items[:MAX_DISPLAYED_PER_RESULT]

    status = "no_result" if hit_count == 0 else "hit"

    return CandidateEvidenceResult(
        source=source,
        query_used=query,
        status=status,
        hit_count=hit_count,
        displayed_count=len(displayed),
        truncated=bool(displayed) and hit_count > len(displayed),
        items=displayed,
    )


# ---------------------------------------------------------------------------
# 总体状态判断
# ---------------------------------------------------------------------------

def _overall_status(results: list[CandidateEvidenceResult]) -> str:
    """根据各个 query/source 的结果汇总出整个候选的总体状态。

    - 有命中 + 有错误 → partial_error
    - 有命中且无错误  → hit
    - 全部错误         → error
    - 全部无结果       → no_result
    """
    statuses = {r.status for r in results}
    if "hit" in statuses and "error" in statuses:
        return "partial_error"
    if "hit" in statuses:
        return "hit"
    if statuses == {"error"}:
        return "error"
    if "error" in statuses:
        return "partial_error"
    return "no_result"


def _sort_evidence_results(
    results: list[CandidateEvidenceResult],
) -> list[CandidateEvidenceResult]:
    """把命中结果放在前面，空结果和局部错误放在后面。"""
    return sorted(results, key=lambda result: RESULT_STATUS_SORT_ORDER[result.status])


async def _collect_query_results(
    *,
    query: str,
    seen_by_source: dict[EvidenceSource, set[tuple[str, str, str]]],
    poem: PoemModel,
    current_line_text: str,
) -> list[CandidateEvidenceResult]:
    """用同一个查询词分别查询典故工具和出处工具。"""
    results: list[CandidateEvidenceResult] = []
    operations = [
        ("cnkgraph_allusion", build_allusion_candidates(query)),
        ("cnkgraph_reference", build_reference_evidences(query)),
    ]

    for source, operation in operations:
        result = await _collect_evidence_result(
            source=source,
            query=query,
            operation=operation,
            seen=seen_by_source[source],
            poem=poem,
            current_line_text=current_line_text,
        )
        results.append(result)

    return results


async def _collect_candidate_evidence(
    *,
    candidate: AllusionCandidateItem,
    poem: PoemModel,
) -> list[CandidateEvidenceResult]:
    """为一个候选查询所有允许的 query_variants，并完成排序。"""
    seen_by_source: dict[EvidenceSource, set[tuple[str, str, str]]] = {
        "cnkgraph_allusion": set(),
        "cnkgraph_reference": set(),
    }
    evidence_results: list[CandidateEvidenceResult] = []

    for query in candidate.query_variants[:MAX_QUERIES_PER_CANDIDATE]:
        query_results = await _collect_query_results(
            query=query,
            seen_by_source=seen_by_source,
            poem=poem,
            current_line_text=candidate.line_text,
        )
        evidence_results.extend(query_results)

    return _sort_evidence_results(evidence_results)


def _candidate_errors(
    candidate: AllusionCandidateItem,
    results: list[CandidateEvidenceResult],
) -> list[str]:
    """把单个候选的局部错误整理成稳定、可读的错误摘要。"""
    errors: list[str] = []
    for result in results:
        if result.status != "error" or not result.error:
            continue
        errors.append(
            f"{candidate.anchor_text} / {result.source} / "
            f"{result.query_used}: {result.error}"
        )
    return errors


def _build_preview_item(
    candidate: AllusionCandidateItem,
    evidence_results: list[CandidateEvidenceResult],
) -> AllusionCandidateEvidenceItem:
    """把候选本身与证据结果合并成接口返回项。"""
    return AllusionCandidateEvidenceItem(
        **candidate.model_dump(),
        evidence_results=evidence_results,
        overall_status=_overall_status(evidence_results),
    )


# ---------------------------------------------------------------------------
# 主入口：为整首词生成候选证据预览
# ---------------------------------------------------------------------------

async def build_allusion_evidence_preview(
    poem: PoemModel,
) -> AllusionCandidateEvidenceResponse:
    """识别整首词的典故候选，并为每个查询变体自动查询 CNKGraph。

    处理流程：
    ① LLM 识别候选
    ② 每个候选取最多 3 个查询变体
    ③ 每个查询变体分别调用 CNKGraph 典故工具和出处工具
    ④ 去重、标记时间关系、排序
    ⑤ 汇总总体状态，收集局部错误
    """
    extracted = await extract_allusion_candidates(poem)

    preview_items: list[AllusionCandidateEvidenceItem] = []
    errors: list[str] = []

    for candidate in extracted.candidates[:10]:
        evidence_results = await _collect_candidate_evidence(
            candidate=candidate,
            poem=poem,
        )
        errors.extend(_candidate_errors(candidate, evidence_results))
        preview_items.append(_build_preview_item(candidate, evidence_results))

    return AllusionCandidateEvidenceResponse(
        poem_id=poem.poem_id,
        items=preview_items,
        errors=errors,
    )
