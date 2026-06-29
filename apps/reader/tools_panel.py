"""Reader 右侧阅读辅助与 AI 审阅工具面板。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from apps.reader.api_client import (
    ReaderAPIError,
    fetch_allusion_candidates,
    fetch_reading_aids,
)
from apps.reader.config import READING_AID_TABS, REVIEW_STATUS_LABELS, TOOL_LABELS
from apps.reader.evidence import (
    all_candidates_have_no_evidence,
    candidate_type_label,
    card_html,
    evidence_preview_html,
    evidence_status_text,
    long_evidence_entries,
    review_evidence_html,
    review_result_html,
)
from apps.reader.state import (
    allusion_candidate_items,
    candidate_selection_payload,
    choose_allusion_candidate,
    choose_line,
)


def render_tools(poem: dict[str, Any]) -> None:
    """展示 AI 候选入口、手动工具表单和证据结果。"""
    st.markdown("### 阅读辅助")
    _render_ai_review_section(poem)
    _render_manual_aids_form(poem)
    render_reading_results(
        st.session_state.get("reading_aids"),
        st.session_state.get("last_included_tools"),
    )
    st.markdown(
        "<div class='future-slot'><strong>AI 综合解释</strong><br>下一版本接入</div>",
        unsafe_allow_html=True,
    )


def _render_ai_review_section(poem: dict[str, Any]) -> None:
    """展示 AI 候选证据审阅入口，以及已返回的候选结果。"""
    if st.button(
        "AI 审阅候选证据并生成短注",
        key=f"extract-allusions-{poem['poem_id']}",
        use_container_width=True,
    ):
        st.session_state.allusion_candidates = None
        st.session_state.allusion_candidate_error = None
        st.session_state.pop("allusion_candidate_selection", None)
        try:
            with st.spinner("正在识别、查证并逐项审阅候选证据"):
                st.session_state.allusion_candidates = fetch_allusion_candidates(
                    poem["poem_id"]
                )
        except ReaderAPIError as exc:
            st.session_state.allusion_candidate_error = str(exc)

    if st.session_state.allusion_candidate_error:
        st.error(st.session_state.allusion_candidate_error)

    candidates = allusion_candidate_items(st.session_state.allusion_candidates)
    if st.session_state.allusion_candidates is not None and not candidates:
        st.markdown(
            "<div class='empty-state'>本词暂未识别到明确的典故候选</div>",
            unsafe_allow_html=True,
        )
    elif candidates:
        _render_candidate_picker(candidates)
        render_allusion_evidence_preview(poem["poem_id"], candidates)


def _render_candidate_picker(candidates: list[dict[str, Any]]) -> None:
    """展示候选 pills，并把选中的 anchor 回填到手动查询框。"""
    candidate_options = [str(index) for index in range(len(candidates))]
    st.pills(
        "候选锚点",
        options=candidate_options,
        key="allusion_candidate_selection",
        format_func=lambda index: candidates[int(index)]["anchor_text"],
        on_change=choose_allusion_candidate,
    )
    selected_candidate = st.session_state.get("allusion_candidate_selection")
    if selected_candidate is None:
        return
    candidate = candidates[int(selected_candidate)]
    st.caption(
        f"第 {candidate['line_no']} 句 · "
        f"{candidate_type_label(str(candidate['candidate_type']))} · "
        f"{candidate['confidence']}：{candidate['reason']}"
    )


def _render_manual_aids_form(poem: dict[str, Any]) -> None:
    """展示手动 reading-aids 表单，并在提交时查询外部候选证据。"""
    with st.form("reading-aids-form", border=True):
        selected_text = st.text_input(
            "选中文本",
            key="selected_text",
            placeholder="兔葵燕麦",
        )
        st.markdown(
            "<div class='query-hint'>建议输入短语，如：章台、前度刘郎、兔葵燕麦。</div>",
            unsafe_allow_html=True,
        )
        selected_labels = st.pills(
            "工具",
            options=list(TOOL_LABELS),
            selection_mode="multi",
            default=list(TOOL_LABELS),
            format_func=lambda key: TOOL_LABELS[key],
        )
        selected_labels = list(selected_labels or [])
        submitted = st.form_submit_button(
            "查询阅读辅助",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        _handle_manual_aids_submission(poem, selected_text, selected_labels)


def _handle_manual_aids_submission(
    poem: dict[str, Any],
    selected_text: str,
    selected_labels: list[str],
) -> None:
    """校验手动查询输入，并调用后端 reading-aids 接口。"""
    normalized_text = selected_text.strip()
    if not normalized_text:
        st.warning("请输入或选择文本")
        return
    if not selected_labels:
        st.warning("请至少选择一个工具")
        return

    line_no = (
        st.session_state.selected_line_no
        if normalized_text == st.session_state.selected_line_text
        else None
    )
    st.session_state.reading_aids = None
    st.session_state.last_included_tools = selected_labels
    try:
        with st.spinner("正在查询外部候选证据"):
            st.session_state.reading_aids = fetch_reading_aids(
                poem["poem_id"],
                normalized_text,
                line_no,
                selected_labels,
            )
    except ReaderAPIError as exc:
        st.error(str(exc))


def render_allusion_evidence_preview(
    poem_id: str,
    candidates: list[dict[str, Any]],
) -> None:
    """展示 Reviewer 结论，并默认折叠原候选证据预览。"""
    if all_candidates_have_no_evidence(candidates):
        st.info("所有候选均未查到外部候选证据；候选仍可用于手动查询。")

    for index, candidate in enumerate(candidates):
        with st.expander(_candidate_expander_title(candidate), expanded=index == 0):
            _render_candidate_header(poem_id, index, candidate)
            review = candidate.get("review_result") or {}
            if review:
                _render_review_block(review)
            _render_raw_evidence_popovers(candidate.get("evidence_results") or [], review)


def _candidate_expander_title(candidate: dict[str, Any]) -> str:
    """生成候选折叠面板标题，展示 anchor 和当前审阅/查证状态。"""
    anchor_text = str(candidate.get("anchor_text") or "未命名候选")
    review = candidate.get("review_result") or {}
    if review:
        status = REVIEW_STATUS_LABELS.get(str(review.get("review_status") or ""), "状态未知")
    else:
        status = evidence_status_text(str(candidate.get("overall_status") or ""), overall=True)
    return f"{anchor_text} · {status}"


def _render_candidate_header(poem_id: str, index: int, candidate: dict[str, Any]) -> None:
    """展示候选锚点、行号、类型、查询变体和谨慎理由。"""
    anchor_text = str(candidate.get("anchor_text") or "未命名候选")
    st.button(
        anchor_text,
        key=f"candidate-anchor-{poem_id}-{index}",
        help="填入下方选中文本",
        on_click=choose_line,
        args=candidate_selection_payload(candidate),
    )
    st.caption(
        f"第 {candidate.get('line_no')} 句 · "
        f"{candidate_type_label(str(candidate.get('candidate_type') or ''))} · "
        f"{candidate.get('confidence')}"
    )
    query_variants = candidate.get("query_variants") or []
    st.caption("查询变体：" + " · ".join(str(value) for value in query_variants))
    st.caption(str(candidate.get("reason") or ""))


def _render_review_block(review: dict[str, Any]) -> None:
    """展示 Review 结论、最佳证据，以及折叠的降级/拒绝证据。"""
    st.markdown(review_result_html(review), unsafe_allow_html=True)
    best = review.get("best_evidence") or []
    if best:
        st.caption("最佳候选证据")
        for item in best:
            st.markdown(review_evidence_html(item), unsafe_allow_html=True)

    secondary = [
        *(review.get("downgraded_evidence") or []),
        *(review.get("rejected_evidence") or []),
    ]
    if not secondary:
        return
    with st.popover(f"查看降级与拒绝证据 · {len(secondary)}"):
        for item in secondary:
            st.markdown(review_evidence_html(item), unsafe_allow_html=True)


def _render_raw_evidence_popovers(
    results: list[dict[str, Any]],
    review: dict[str, Any],
) -> None:
    """折叠展示原候选证据预览和长引文；没有结果时显示空态。"""
    if not results:
        if not review:
            st.markdown(
                "<div class='empty-state'>尚无候选证据结果</div>",
                unsafe_allow_html=True,
            )
        return

    with st.popover("查看原候选证据预览"):
        for result in results:
            st.markdown(evidence_preview_html(result), unsafe_allow_html=True)

    long_entries = [entry for result in results for entry in long_evidence_entries(result)]
    if not long_entries:
        return
    with st.popover(f"查看候选证据长引文 · {len(long_entries)}"):
        for title, full_text in long_entries:
            st.caption(title)
            st.text(full_text)


def render_evidences(items: list[dict[str, Any]]) -> None:
    """展示手动 reading-aids 返回的通用证据卡片。"""
    if not items:
        st.markdown("<div class='empty-state'>暂无候选</div>", unsafe_allow_html=True)
        return
    for item in items:
        st.markdown(
            card_html(
                anchor_text=item.get("anchor_text"),
                title=item.get("title"),
                body=item.get("claim"),
                detail=item.get("evidence_text"),
                source_ref=item.get("source_ref"),
                source=item.get("source") or "cnkgraph",
            ),
            unsafe_allow_html=True,
        )


def render_allusions(items: list[dict[str, Any]]) -> None:
    """展示手动 reading-aids 返回的典故候选卡片。"""
    if not items:
        st.markdown("<div class='empty-state'>暂无候选</div>", unsafe_allow_html=True)
        return
    for item in items:
        st.markdown(
            card_html(
                anchor_text=item.get("keyword"),
                title=item.get("title"),
                body=item.get("explanation"),
                detail=item.get("source_text"),
                source_ref=item.get("source_ref"),
            ),
            unsafe_allow_html=True,
        )


def _group_tool_errors(errors: list[str]) -> dict[str, list[str]]:
    """按 reading-aids 使用的工具前缀整理局部错误。"""
    grouped: dict[str, list[str]] = {}
    for error in errors:
        prefix, separator, detail = error.partition(":")
        tool_name = prefix.split("[", 1)[0]
        if separator and tool_name in TOOL_LABELS:
            grouped.setdefault(tool_name, []).append(detail.strip())
    return grouped


def render_tool_status(tool_name: str, errors: list[str], has_items: bool) -> None:
    """在对应工具分区内解释空结果或局部上游失败。"""
    if not errors:
        return
    if all("HTTP 404" in error for error in errors):
        message = "部分内容未匹配" if has_items else "暂无匹配结果"
    else:
        message = "部分查询暂不可用" if has_items else "CNKGraph 暂时无法完成此项查询"
    st.markdown(
        f"<div class='tool-status'>{TOOL_LABELS[tool_name]}：{message}</div>",
        unsafe_allow_html=True,
    )


def _organize_aids_data(data: dict[str, Any]) -> dict[str, Any]:
    """把后端 reading-aids 响应按工具分组，并计算错误汇总信息。"""
    evidences = data.get("evidences", [])
    by_tool = {
        tool_name: [item for item in evidences if item.get("tool_name") == tool_name]
        for tool_name in ("char", "reference", "ci_tune")
    }
    rhyme_items = (data.get("prosody") or {}).get("rhyme_info", [])
    allusions = data.get("allusions", [])
    errors_by_tool = _group_tool_errors(data.get("errors", []))

    return {
        "by_tool": by_tool,
        "rhyme_items": rhyme_items,
        "allusions": allusions,
        "result_count": len(evidences) + len(rhyme_items) + len(allusions),
        "errors_by_tool": errors_by_tool,
        "hard_error_tools": {
            tool_name
            for tool_name, errors in errors_by_tool.items()
            if any("HTTP 404" not in error for error in errors)
        },
    }


def render_reading_results(
    data: dict[str, Any] | None,
    included_tools: list[str] | None,
) -> None:
    """按工具类型展示窄模型字段，忽略 raw。"""
    if not data:
        st.markdown("<div class='empty-state'>尚未查询</div>", unsafe_allow_html=True)
        return

    organized = _organize_aids_data(data)
    included = set(included_tools or TOOL_LABELS)

    if (
        included
        and organized["result_count"] == 0
        and included.issubset(organized["hard_error_tools"])
    ):
        st.error("本次所选工具均暂时不可用，正文仍可继续阅读。")

    by_tool = organized["by_tool"]
    errors_by_tool = organized["errors_by_tool"]
    tab_payloads = {
        "char": (by_tool["char"], render_evidences),
        "allusion": (organized["allusions"], render_allusions),
        "reference": (by_tool["reference"], render_evidences),
        "rhyme": (organized["rhyme_items"], render_evidences),
        "ci_tune": (by_tool["ci_tune"], render_evidences),
    }
    tabs = st.tabs([label for _, label in READING_AID_TABS])
    for tab, (tool_name, _) in zip(tabs, READING_AID_TABS):
        items, renderer = tab_payloads[tool_name]
        with tab:
            if tool_name not in included:
                st.markdown(
                    "<div class='empty-state'>本次未查询</div>",
                    unsafe_allow_html=True,
                )
                continue
            render_tool_status(
                tool_name,
                errors_by_tool.get(tool_name, []),
                bool(items),
            )
            renderer(items)
