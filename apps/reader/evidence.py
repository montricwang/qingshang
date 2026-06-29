"""Reader 的证据展示整理函数。

这个模块是"HTML 模板层"：把后端返回的 dict 数据转成安全的 HTML 片段。
所有函数都做 html.escape()，因为 Streamlit 的 unsafe_allow_html=True 不做自动转义。

注意：这里不调用 Streamlit（st.xxx），只返回 HTML 字符串，方便单元测试。
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


# ========================================================================
# 状态码 → 中文展示文案
# ========================================================================

def evidence_status_text(status: str, *, overall: bool = False) -> str:
    """把接口状态码式字符串翻译成 Reader 展示文案。

    overall=True 时使用全局级别的标签（查到了/未查到/部分失败/全失败），
    overall=False 时使用单条查询级别的标签（命中/无结果/错误）。
    """
    labels = OVERALL_STATUS_LABELS if overall else EVIDENCE_STATUS_LABELS
    return labels.get(status, "状态未知")


def candidate_type_label(candidate_type: str) -> str:
    """把后端候选类型枚举翻译成中文。"""
    return CANDIDATE_TYPE_LABELS.get(candidate_type, "待查")


# ========================================================================
# 文本截断
# ========================================================================

def truncate_evidence_text(
    text: str | None,
    *,
    limit: int = EVIDENCE_EXCERPT_LIMIT,
) -> tuple[str, str | None]:
    """长引文截断，返回（摘要文本, 完整文本或 None）。

    例如：原文 300 字、limit=160 → 返回 ("前160字…", "完整300字")
    原文 100 字、limit=160 → 返回 ("完整100字", None)
    """
    if not text:
        return "", None
    normalized = str(text)
    if len(normalized) <= limit:
        return normalized, None
    return normalized[:limit] + "…", normalized


# ========================================================================
# 证据结果统计
# ========================================================================

def evidence_count_text(result: dict[str, Any]) -> str:
    """生成命中数、展示数和截断状态。

    避免"展示 0 但已截断"的矛盾表述：
    - 命中>0 但展示=0 → "暂无可展示条目"
    - 展示>0 且有截断标记 → "命中/展示/已截断"
    - 正常情况 → "命中/展示"
    """
    hit_count = int(result.get("hit_count") or 0)
    displayed_count = int(result.get("displayed_count") or 0)

    if hit_count > 0 and displayed_count == 0:
        return f"命中 {hit_count} · 暂无可展示条目"
    if displayed_count > 0 and result.get("truncated") and hit_count > displayed_count:
        return f"命中 {hit_count} · 展示 {displayed_count} · 已截断"
    return f"命中 {hit_count} · 展示 {displayed_count}"


# ========================================================================
# 证据预览 HTML（自动查证阶段的显示）
# ========================================================================

def evidence_preview_html(result: dict[str, Any]) -> str:
    """渲染一个 query/source 组合的候选证据预览卡片。

    包含：来源名称、查询状态、查询词、命中统计、逐条证据摘要。
    """
    parts = [
        "<div class='evidence-preview'>",
        _evidence_preview_header(result),
    ]

    if result.get("error"):
        parts.append(
            f"<div class='evidence-preview-error'>{html.escape(str(result['error']))}</div>"
        )

    for item in result.get("items", []):
        parts.append(_evidence_preview_item_html(item))

    parts.append("</div>")
    return "".join(parts)


def _evidence_preview_header(result: dict[str, Any]) -> str:
    """生成候选证据预览卡片的标题与命中统计。"""
    source = EVIDENCE_SOURCE_LABELS.get(
        str(result.get("source") or ""),
        str(result.get("source") or "未知来源"),
    )
    status = evidence_status_text(str(result.get("status") or ""))
    query = html.escape(str(result.get("query_used") or ""))
    return (
        f"<div class='evidence-preview-head'>{html.escape(source)} · "
        f"{html.escape(status)}</div>"
        f"<div class='evidence-preview-meta'>查询：{query} · "
        f"{evidence_count_text(result)}</div>"
    )


def _evidence_context_html(item: dict[str, Any]) -> str:
    """生成前代来源、当前作品命中、后代用例等谨慎标记。"""
    relation = EVIDENCE_CONTEXT_LABELS.get(str(item.get("context_relation") or ""))
    return f"<br><strong>{html.escape(relation)}</strong>" if relation else ""


def _evidence_detail_html(item: dict[str, Any], excerpt: str) -> str:
    """拼接一条证据的摘要、命中片段和来源信息。"""
    detail_values = [
        item.get("claim"),
        f"命中片段：{item['anchor_text']}" if item.get("anchor_text") else None,
        excerpt or None,
        item.get("source_ref"),
    ]
    return "<br>".join(html.escape(str(value)) for value in detail_values if value)


def _evidence_preview_item_html(item: dict[str, Any]) -> str:
    """生成候选证据预览中的单条证据 HTML。"""
    title = html.escape(str(item.get("title") or "未命名候选"))
    excerpt, full_text = truncate_evidence_text(item.get("evidence_text"))
    details = _evidence_detail_html(item, excerpt)
    folded_note = "<br><em>长引文已折叠</em>" if full_text else ""

    return (
        "<div class='evidence-preview-item'>"
        f"<strong>{title}</strong>"
        f"{_evidence_context_html(item)}"
        f"{'<br>' + details if details else ''}"
        f"{folded_note}"
        "</div>"
    )


def long_evidence_entries(result: dict[str, Any]) -> list[tuple[str, str]]:
    """收集需要由折叠控件展示的长引文。

    返回 [(标题, 完整文本), ...]，供折叠组件按条展示。
    """
    entries: list[tuple[str, str]] = []
    for item in result.get("items", []):
        _, full_text = truncate_evidence_text(item.get("evidence_text"))
        if full_text:
            entries.append((str(item.get("title") or "未命名候选"), full_text))
    return entries


def all_candidates_have_no_evidence(candidates: list[dict[str, Any]]) -> bool:
    """判断是否所有候选都查过了但没有任何外部命中。"""
    return bool(candidates) and all(
        candidate.get("overall_status") == "no_result" for candidate in candidates
    )


# ========================================================================
# 证据审阅结果 HTML（LLM Review 阶段的显示）
# ========================================================================

def review_evidence_html(item: dict[str, Any]) -> str:
    """渲染 Reviewer 对一条实际证据的分类。

    展示：证据标题、角色（前代/自引用/后代）、相关度、审阅理由、查询词、来源。
    所有从 LLM 来的文本都先做 HTML 转义。
    """
    title = html.escape(str(item.get("title") or "未命名候选"))
    role = html.escape(REVIEW_ROLE_LABELS.get(str(item.get("role") or ""), "关系不明"))
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
    """生成审阅状态与短注摘要。

    注意：短注不是最终人工定论，仅展示审阅器基于已有证据的判断。
    """
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
        "<div class='evidence-preview-item'>"
        f"<strong>审阅短注</strong><br>{short_note}"
        f"{'<br><em>' + caveat + '</em>' if caveat else ''}"
        "</div></div>"
    )


# ========================================================================
# 手动阅读辅助结果卡片
# ========================================================================

def card_html(
    *,
    anchor_text: str | None,
    title: str | None,
    body: str | None,
    detail: str | None,
    source_ref: str | None,
    source: str = "cnkgraph",
) -> str:
    """生成手动 reading-aids 的通用证据卡片。

    用于字词释义、出处与化用、韵部、词谱等各类型结果的统一展示。
    """
    anchor = html.escape(anchor_text or "当前文本")
    title_html = html.escape(title or "未命名候选")
    body_parts = [html.escape(v) for v in (body, detail) if v]
    body_html = "<br>".join(body_parts) or "暂无摘要"
    source_text = " · ".join(html.escape(v) for v in (source, source_ref) if v)

    return (
        "<div class='evidence-card'>"
        f"<div class='evidence-anchor'>{anchor}</div>"
        f"<div class='evidence-title'>{title_html}</div>"
        f"<div class='evidence-body'>{body_html}</div>"
        f"<div class='evidence-source'>{source_text}</div>"
        "</div>"
    )
