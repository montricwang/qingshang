"""Reader 的证据展示整理函数。

这些函数把候选、证据、审阅结果整理成安全的 HTML 片段。它们不调用
Streamlit，也不请求后端，所以适合单元测试。
"""

from __future__ import annotations

import html
from typing import Any

from apps.reader.config import (
    CANDIDATE_TYPE_LABELS,
    EVIDENCE_CONTEXT_LABELS,
    EVIDENCE_EXCERPT_LIMIT,
    EVIDENCE_SOURCE_LABELS,
    EVIDENCE_STATUS_LABELS,
    OVERALL_STATUS_LABELS,
    REVIEW_ROLE_LABELS,
    REVIEW_STATUS_LABELS,
)


def evidence_status_text(status: str, *, overall: bool = False) -> str:
    """把接口状态码式字符串翻译成 Reader 展示文案。"""
    labels = OVERALL_STATUS_LABELS if overall else EVIDENCE_STATUS_LABELS
    return labels.get(status, "状态未知")


def candidate_type_label(candidate_type: str) -> str:
    """把后端候选类型枚举翻译成中文。"""
    return CANDIDATE_TYPE_LABELS.get(candidate_type, "待查")


def truncate_evidence_text(
    text: str | None,
    *,
    limit: int = EVIDENCE_EXCERPT_LIMIT,
) -> tuple[str, str | None]:
    """长引文默认截断展示，完整文本交给折叠控件。"""
    if not text:
        return "", None
    normalized = str(text)
    if len(normalized) <= limit:
        return normalized, None
    return normalized[:limit] + "…", normalized


def evidence_count_text(result: dict[str, Any]) -> str:
    """生成命中数、展示数和截断状态，避免“展示 0 但已截断”的矛盾。"""
    hit_count = int(result.get("hit_count") or 0)
    displayed_count = int(result.get("displayed_count") or 0)
    if hit_count > 0 and displayed_count == 0:
        return f"命中 {hit_count} · 暂无可展示条目"
    if displayed_count > 0 and result.get("truncated") and hit_count > displayed_count:
        return f"命中 {hit_count} · 展示 {displayed_count} · 已截断"
    return f"命中 {hit_count} · 展示 {displayed_count}"


def evidence_preview_html(result: dict[str, Any]) -> str:
    """渲染一个 query/source 的候选证据预览。"""
    source = EVIDENCE_SOURCE_LABELS.get(
        str(result.get("source") or ""),
        str(result.get("source") or "未知来源"),
    )
    status = evidence_status_text(str(result.get("status") or ""))
    query = html.escape(str(result.get("query_used") or ""))
    parts = [
        "<div class='evidence-preview'>",
        (
            "<div class='evidence-preview-head'>"
            f"{html.escape(source)} · {html.escape(status)}</div>"
        ),
        (
            "<div class='evidence-preview-meta'>"
            f"查询：{query} · {evidence_count_text(result)}</div>"
        ),
    ]
    if result.get("error"):
        parts.append(
            "<div class='evidence-preview-error'>"
            f"{html.escape(str(result['error']))}</div>"
        )
    for item in result.get("items", []):
        title = html.escape(str(item.get("title") or "未命名候选"))
        excerpt, full_text = truncate_evidence_text(item.get("evidence_text"))
        relation = EVIDENCE_CONTEXT_LABELS.get(str(item.get("context_relation") or ""))
        relation_html = (
            f"<br><strong>{html.escape(relation)}</strong>" if relation else ""
        )
        details = "<br>".join(
            html.escape(str(value))
            for value in (
                item.get("claim"),
                f"命中片段：{item['anchor_text']}" if item.get("anchor_text") else None,
                excerpt or None,
                item.get("source_ref"),
            )
            if value
        )
        parts.append(
            "<div class='evidence-preview-item'>"
            f"<strong>{title}</strong>"
            f"{relation_html}"
            f"{'<br>' + details if details else ''}"
            f"{'<br><em>长引文已折叠</em>' if full_text else ''}</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def long_evidence_entries(result: dict[str, Any]) -> list[tuple[str, str]]:
    """收集需要由折叠控件展示的长引文。"""
    entries: list[tuple[str, str]] = []
    for item in result.get("items", []):
        _, full_text = truncate_evidence_text(item.get("evidence_text"))
        if full_text:
            entries.append((str(item.get("title") or "未命名候选"), full_text))
    return entries


def all_candidates_have_no_evidence(candidates: list[dict[str, Any]]) -> bool:
    """判断是否所有候选都完整查过但没有任何外部命中。"""
    return bool(candidates) and all(
        candidate.get("overall_status") == "no_result" for candidate in candidates
    )


def review_evidence_html(item: dict[str, Any]) -> str:
    """渲染 Reviewer 对一条实际证据的分类，所有模型文本先转义。"""
    title = html.escape(str(item.get("title") or "未命名候选"))
    role = html.escape(
        REVIEW_ROLE_LABELS.get(str(item.get("role") or ""), "关系不明")
    )
    relevance = html.escape(str(item.get("relevance") or "unknown"))
    reason = html.escape(str(item.get("reason") or "暂无审阅理由"))
    source_ref = html.escape(str(item.get("source_ref") or ""))
    query = html.escape(str(item.get("query_used") or ""))
    return (
        "<div class='evidence-preview-item'>"
        f"<strong>{title}</strong><br>"
        f"{role} · 相关度 {relevance}<br>"
        f"{reason}<br>"
        f"查询：{query}"
        f"{'<br>' + source_ref if source_ref else ''}"
        "</div>"
    )


def review_result_html(review: dict[str, Any]) -> str:
    """生成审阅状态与短注摘要，不把短注表述为最终定论。"""
    status = html.escape(
        REVIEW_STATUS_LABELS.get(str(review.get("review_status") or ""), "状态未知")
    )
    confidence = html.escape(str(review.get("confidence") or "low"))
    short_note = html.escape(str(review.get("short_note") or "未生成审阅短注"))
    caveat = html.escape(str(review.get("caveat") or ""))
    return (
        "<div class='evidence-preview'>"
        f"<div class='evidence-preview-head'>Evidence Review · {status}</div>"
        f"<div class='evidence-preview-meta'>置信度：{confidence}</div>"
        f"<div class='evidence-preview-item'><strong>审阅短注</strong><br>{short_note}"
        f"{'<br><em>' + caveat + '</em>' if caveat else ''}</div>"
        "</div>"
    )


def card_html(
    *,
    anchor_text: str | None,
    title: str | None,
    body: str | None,
    detail: str | None,
    source_ref: str | None,
    source: str = "cnkgraph",
) -> str:
    """生成手动 reading-aids 结果卡片。"""
    anchor = html.escape(anchor_text or "当前文本")
    title_html = html.escape(title or "未命名候选")
    body_parts = [html.escape(value) for value in (body, detail) if value]
    body_html = "<br>".join(body_parts) or "暂无摘要"
    source_text = " · ".join(
        html.escape(value) for value in (source, source_ref) if value
    )
    return (
        "<div class='evidence-card'>"
        f"<div class='evidence-anchor'>{anchor}</div>"
        f"<div class='evidence-title'>{title_html}</div>"
        f"<div class='evidence-body'>{body_html}</div>"
        f"<div class='evidence-source'>{source_text}</div>"
        "</div>"
    )

