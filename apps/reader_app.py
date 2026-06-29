"""清商 Reader v0.2.0：本地词作阅读与候选证据审阅短注。"""

from __future__ import annotations

import base64
import time
from typing import Any

import streamlit as st

from apps.reader.api_client import (
    ReaderAPIError,
    fetch_allusion_candidates,
    fetch_opening_lines,
    fetch_poem,
    fetch_poems,
    fetch_reading_aids,
)
from apps.reader.config import (
    DIRECTORY_PAGE_SIZE,
    HERO_IMAGE,
    READING_MODES,
    REVIEW_STATUS_LABELS,
    SPEED_SECONDS,
    THEME_PALETTES,
    TOOL_LABELS,
)
from apps.reader.evidence import (
    all_candidates_have_no_evidence as _all_candidates_have_no_evidence,
    candidate_type_label as _candidate_type_label,
    card_html as _card_html,
    evidence_count_text as _evidence_count_text,
    evidence_preview_html as _evidence_preview_html,
    evidence_status_text as _evidence_status_text,
    long_evidence_entries as _long_evidence_entries,
    review_evidence_html as _review_evidence_html,
    review_result_html as _review_result_html,
    truncate_evidence_text as _truncate_evidence_text,
)
from apps.reader.state import (
    allusion_candidate_items as _allusion_candidate_items,
    candidate_selection_payload as _candidate_selection_payload,
    change_directory_page,
    change_reading_mode,
    choose_allusion_candidate,
    choose_line,
    choose_poem,
    initialize_state,
    maybe_advance_guided_line,
    move_focus_line,
    reset_directory_page,
    reset_guided_clock,
    toggle_guided_playback,
)
from apps.reader.text import (
    bounded_line_index,
    build_breathing_fragments,
    flatten_poem_lines,
    strip_trailing_pause as _strip_trailing_pause,
)


def install_styles(theme_name: str) -> None:
    """应用 Reader 的稳定布局和领域视觉样式。"""
    palette = THEME_PALETTES[theme_name]
    variables = "\n".join(
        f"--qs-{name.replace('_', '-')}: {value};" for name, value in palette.items()
    )
    st.markdown(
        """<style>"""
        + f":root {{ {variables} }}"
        + """
        .stApp { background: var(--qs-app-bg); color: var(--qs-text); }
        [data-testid="stSidebar"] {
            background: var(--qs-sidebar-bg);
            border-right: 1px solid var(--qs-border);
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button {
            min-height: 2.15rem;
            padding: 0.28rem 0.55rem;
            text-align: left;
            justify-content: flex-start;
            border-radius: 4px;
            letter-spacing: 0;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: var(--qs-text-muted);
            font-size: 0.78rem;
            line-height: 1.3;
            margin: -0.34rem 0 0.14rem 0.3rem;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.34rem;
        }
        [class*="st-key-directory-"] button {
            min-height: 1.95rem !important;
            padding-bottom: 0.15rem !important;
            padding-top: 0.15rem !important;
        }
        .block-container {
            max-width: 1480px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }
        .reader-hero {
            height: 148px;
            background-color: var(--qs-hero-tint);
            background-blend-mode: var(--qs-hero-blend);
            background-size: cover;
            background-position: center;
            border: 1px solid var(--qs-border);
            border-radius: 6px;
            margin-bottom: 1.2rem;
            padding: 28px 36px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .reader-brand {
            color: var(--qs-text);
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            font-size: 2.25rem;
            font-weight: 700;
            line-height: 1.1;
            letter-spacing: 0;
        }
        .reader-version {
            color: var(--qs-accent);
            font-size: 0.8rem;
            margin-top: 0.55rem;
            letter-spacing: 0;
        }
        .poem-heading {
            border-bottom: 1px solid var(--qs-border);
            padding: 0.25rem 0 1rem;
            margin-bottom: 1.2rem;
        }
        .poem-tune {
            color: var(--qs-text);
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            font-size: 1.75rem;
            font-weight: 700;
            line-height: 1.25;
            letter-spacing: 0;
        }
        .poem-title { color: var(--qs-text-muted); font-weight: 400; }
        .poem-meta { color: var(--qs-text-muted); font-size: 0.9rem; margin-top: 0.45rem; }
        .poem-preface {
            color: var(--qs-text-muted);
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            line-height: 1.9;
            padding: 0.7rem 0;
        }
        .section-break {
            background: var(--qs-border-soft);
            height: 1px;
            margin: 1.25rem 12% 0.75rem;
            opacity: 0.4;
        }
        .evidence-card {
            background: var(--qs-surface);
            border: 1px solid var(--qs-border);
            border-left: 3px solid var(--qs-green);
            border-radius: 5px;
            padding: 0.85rem 0.95rem;
            margin: 0.55rem 0;
            overflow-wrap: anywhere;
        }
        .evidence-anchor { color: var(--qs-accent); font-size: 0.78rem; font-weight: 700; }
        .evidence-title { color: var(--qs-text); font-weight: 700; margin: 0.25rem 0; }
        .evidence-body { color: var(--qs-text); font-size: 0.9rem; line-height: 1.65; }
        .evidence-source {
            color: var(--qs-text-muted);
            border-top: 1px solid var(--qs-border-soft);
            font-size: 0.75rem;
            margin-top: 0.6rem;
            padding-top: 0.5rem;
        }
        .evidence-preview {
            border-top: 1px solid var(--qs-border-soft);
            margin-top: 0.7rem;
            padding-top: 0.65rem;
        }
        .evidence-preview-head { color: var(--qs-text); font-size: 0.84rem; }
        .evidence-preview-meta { color: var(--qs-text-muted); font-size: 0.75rem; }
        .evidence-preview-item {
            color: var(--qs-text);
            font-size: 0.82rem;
            line-height: 1.55;
            margin-top: 0.5rem;
            padding-left: 0.65rem;
            border-left: 2px solid var(--qs-green);
        }
        .evidence-preview-error { color: var(--qs-accent); font-size: 0.8rem; }
        .empty-state {
            color: var(--qs-text-muted);
            border: 1px dashed var(--qs-border);
            border-radius: 5px;
            padding: 0.9rem;
            margin: 0.5rem 0;
        }
        .future-slot {
            background: var(--qs-surface-muted);
            border: 1px solid var(--qs-border);
            border-radius: 5px;
            color: var(--qs-text-muted);
            padding: 0.75rem 0.85rem;
            margin-top: 0.65rem;
            font-size: 0.83rem;
        }
        .future-slot strong { color: var(--qs-text); }
        .tool-status {
            background: var(--qs-surface-muted);
            border-left: 2px solid var(--qs-border);
            color: var(--qs-text-muted);
            font-size: 0.82rem;
            margin: 0.5rem 0;
            padding: 0.65rem 0.75rem;
        }
        .query-hint { color: var(--qs-text-muted); font-size: 0.78rem; margin: -0.35rem 0 0.8rem; }
        [data-testid="stForm"] {
            background: var(--qs-surface);
            border-radius: 6px;
            border-color: var(--qs-border);
            color: var(--qs-text);
        }
        [data-testid="stTextInput"] [data-baseweb="input"],
        [data-testid="stTextInput"] input,
        [data-testid="stTextInput"] div,
        [data-baseweb="select"] > div {
            background-color: var(--qs-surface) !important;
            color: var(--qs-text) !important;
        }
        [data-testid="stTextInput"] [data-baseweb="input"],
        [data-baseweb="select"] > div {
            border-color: var(--qs-border) !important;
        }
        [data-testid="stTextInput"] input::placeholder {
            color: var(--qs-text-muted) !important;
            opacity: 0.82;
        }
        [data-testid="stTextInput"]:focus-within [data-baseweb="input"],
        [data-testid="stTextInput"] [data-baseweb="base-input"]:focus-within,
        [data-baseweb="select"] > div:focus-within {
            border-color: var(--qs-accent) !important;
            box-shadow: 0 0 0 1px var(--qs-accent) !important;
            outline: 1px solid var(--qs-accent) !important;
            outline-offset: -1px;
        }
        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="menu"],
        [role="listbox"] {
            background-color: var(--qs-surface) !important;
            border-color: var(--qs-border) !important;
            color: var(--qs-text) !important;
        }
        [data-baseweb="menu"] li,
        [role="option"] {
            background-color: var(--qs-surface) !important;
            color: var(--qs-text) !important;
        }
        [data-baseweb="menu"] li:hover,
        [role="option"]:hover {
            background-color: var(--qs-surface-muted) !important;
        }
        [data-testid="stButtonGroup"] button[data-testid^="stBaseButton-pills"] {
            background: var(--qs-surface-muted) !important;
            border: 1px solid var(--qs-border) !important;
            color: var(--qs-text-muted) !important;
            min-height: 2rem;
        }
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-pillsActive"] {
            background: var(--qs-accent-soft) !important;
            border-color: var(--qs-accent) !important;
            color: var(--qs-accent) !important;
        }
        [data-testid="stTabs"] button {
            color: var(--qs-text-muted);
            letter-spacing: 0;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--qs-accent);
            border-bottom-color: var(--qs-accent);
        }
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button {
            background: transparent;
            border-color: var(--qs-border);
            border-radius: 4px;
            color: var(--qs-text);
            letter-spacing: 0;
        }
        button[kind="primary"], button[kind="primaryFormSubmit"] {
            background: var(--qs-accent-soft) !important;
            border-color: var(--qs-accent) !important;
            color: var(--qs-accent) !important;
        }
        button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
            background: var(--qs-accent-soft) !important;
            border-color: var(--qs-accent-hover) !important;
            color: var(--qs-accent-hover) !important;
        }
        [class*="st-key-line-"] button {
            background: transparent;
            border-color: transparent;
            color: var(--qs-text);
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            font-size: 1rem;
            font-weight: 400;
            min-height: 2.55rem;
            padding-left: 0.7rem;
            justify-content: flex-start;
            text-align: left;
        }
        [class*="st-key-line-"] button p {
            text-align: left;
            white-space: pre-wrap;
            width: 100%;
        }
        [class*="st-key-line-"] button:hover {
            background: var(--qs-surface-muted);
            border-color: var(--qs-border);
            color: var(--qs-text);
        }
        [class*="st-key-line-"] button[kind="primary"] {
            background: var(--qs-accent-soft) !important;
            border-color: transparent !important;
            color: var(--qs-accent) !important;
            box-shadow: inset 2px 0 0 var(--qs-accent);
        }
        [class*="st-key-line-overview-"] button,
        [class*="st-key-line-overview-"] button p {
            justify-content: center;
            text-align: center;
        }
        .focus-reader {
            min-height: 18rem;
            padding: 2.5rem 0 1.5rem;
        }
        .focus-context {
            color: var(--qs-text-muted);
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            min-height: 3.2rem;
            opacity: 0.38;
            padding: 0.85rem 1rem;
            text-align: center;
        }
        .focus-position {
            color: var(--qs-text-muted);
            font-size: 0.75rem;
            margin: 0.7rem 0;
            text-align: center;
        }
        [class*="st-key-focus-current-"] button {
            animation: qs-focus-in 220ms ease-out;
            background: var(--qs-accent-soft) !important;
            border-color: transparent !important;
            color: var(--qs-text) !important;
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            font-size: 1.2rem;
            justify-content: center;
            min-height: 4.4rem;
            padding: 1rem 1.4rem;
            text-align: center;
        }
        [class*="st-key-focus-current-"] button p { text-align: center; }
        [class*="st-key-focus-nav-"] button { min-height: 2.25rem; }
        @keyframes qs-focus-in {
            from { opacity: 0.45; }
            to { opacity: 1; }
        }
        @media (max-width: 900px) {
            .block-container { padding-left: 1rem; padding-right: 1rem; }
            .reader-hero { height: 128px; padding: 22px; background-position: 56% center; }
            .reader-brand { font-size: 1.8rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    """显示项目标识和宋画风横幅。"""
    encoded = base64.b64encode(HERO_IMAGE.read_bytes()).decode("ascii")
    st.markdown(
        f"""
        <div class="reader-hero" style="background-image: url('data:image/webp;base64,{encoded}')">
            <div class="reader-brand">清商</div>
            <div class="reader-version">Reader v0.2.0 · 周邦彦词作</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _poem_label(poem: dict[str, Any]) -> str:
    title = poem.get("title")
    tune_name = poem.get("tune_name") or "未题词牌"
    series_label = poem.get("series_label")
    suffix = " · ".join(value for value in (title, series_label) if value)
    return f"{tune_name} · {suffix}" if suffix else tune_name


def render_poem_directory(poems: list[dict[str, Any]]) -> None:
    """在侧栏展示可筛选的周邦彦词作目录。"""
    st.sidebar.markdown("## 词作目录")
    query = st.sidebar.text_input(
        "筛选",
        placeholder="词牌或题名",
        key="directory_query",
        on_change=reset_directory_page,
    )
    normalized = query.strip().casefold()
    filtered = [
        poem
        for poem in poems
        if not normalized or normalized in _poem_label(poem).casefold()
    ]
    page_count = max(1, (len(filtered) + DIRECTORY_PAGE_SIZE - 1) // DIRECTORY_PAGE_SIZE)
    st.session_state.directory_page = min(
        max(st.session_state.directory_page, 0),
        page_count - 1,
    )
    page = st.session_state.directory_page
    start = page * DIRECTORY_PAGE_SIZE
    visible_poems = filtered[start : start + DIRECTORY_PAGE_SIZE]
    untitled_ids = tuple(poem["poem_id"] for poem in visible_poems if not poem.get("title"))
    opening_lines = fetch_opening_lines(untitled_ids) if untitled_ids else {}

    st.sidebar.caption(f"{len(filtered)} 首 · 第 {page + 1}/{page_count} 页")
    previous_column, next_column = st.sidebar.columns(2)
    previous_column.button(
        "上一页",
        key="directory-previous",
        disabled=page == 0,
        use_container_width=True,
        on_click=change_directory_page,
        args=(-1,),
    )
    next_column.button(
        "下一页",
        key="directory-next",
        disabled=page >= page_count - 1,
        use_container_width=True,
        on_click=change_directory_page,
        args=(1,),
    )

    for poem in visible_poems:
        poem_id = poem["poem_id"]
        st.sidebar.button(
            _poem_label(poem),
            key=f"poem-{poem_id}",
            type="primary" if poem_id == st.session_state.poem_id else "secondary",
            use_container_width=True,
            on_click=choose_poem,
            args=(poem_id,),
        )
        if not poem.get("title") and opening_lines.get(poem_id):
            st.sidebar.caption(_strip_trailing_pause(opening_lines[poem_id]))


def render_section_break(section_index: int) -> None:
    if section_index:
        st.markdown("<div class='section-break'></div>", unsafe_allow_html=True)


def render_overview_mode(poem: dict[str, Any]) -> None:
    """居中展示完整原始词句，适合连续通读。"""
    for section_index, section in enumerate(poem.get("sections", [])):
        render_section_break(section_index)
        for line in section.get("lines", []):
            line_no = line["global_line_no"]
            line_text = line["text"]
            selected = (
                line_no == st.session_state.selected_line_no
                and line_text == st.session_state.selected_line_text
            )
            st.button(
                line_text,
                key=f"line-overview-{poem['poem_id']}-{line_no}",
                type="primary" if selected else "secondary",
                use_container_width=True,
                on_click=choose_line,
                args=(line_no, line_text),
            )


def render_slow_mode(poem: dict[str, Any]) -> None:
    """按句读分片与全角空格缩进展示慢读正文。"""
    sections = build_breathing_fragments(poem.get("sections", []))
    for section_index, fragments in enumerate(sections):
        render_section_break(section_index)
        for fragment in fragments:
            selected = (
                fragment["line_no"] == st.session_state.selected_line_no
                and fragment["text"] == st.session_state.selected_line_text
            )
            st.button(
                fragment["display_text"],
                key=(
                    f"line-fragment-{poem['poem_id']}-{fragment['line_no']}"
                    f"-{fragment['fragment_no']}"
                ),
                type="primary" if selected else "secondary",
                use_container_width=True,
                on_click=choose_line,
                args=(fragment["line_no"], fragment["text"]),
            )


def render_focus_reader(
    lines: list[dict[str, Any]],
    *,
    key_prefix: str,
    show_playback: bool,
) -> None:
    """突出当前原始词句，并以低透明度提供上下文。"""
    if not lines:
        return

    line_count = len(lines)
    current_index = bounded_line_index(
        st.session_state.current_line_index,
        0,
        line_count,
    )
    st.session_state.current_line_index = current_index
    current_line = lines[current_index]
    previous_text = lines[current_index - 1]["text"] if current_index else ""
    next_text = lines[current_index + 1]["text"] if current_index + 1 < line_count else ""

    st.markdown(
        f"<div class='focus-context'>{html.escape(previous_text) or '&nbsp;'}</div>",
        unsafe_allow_html=True,
    )
    st.button(
        current_line["text"],
        key=f"focus-current-{key_prefix}-{current_index}",
        type="primary",
        use_container_width=True,
        on_click=choose_line,
        args=(current_line["global_line_no"], current_line["text"]),
    )
    st.markdown(
        f"<div class='focus-context'>{html.escape(next_text) or '&nbsp;'}</div>",
        unsafe_allow_html=True,
    )

    previous_column, center_column, next_column = st.columns([1, 1, 1])
    previous_column.button(
        "上一句",
        key=f"focus-nav-{key_prefix}-previous",
        disabled=current_index == 0,
        use_container_width=True,
        on_click=move_focus_line,
        args=(-1, line_count),
    )
    if show_playback:
        center_column.button(
            "暂停" if st.session_state.is_playing else "播放",
            key=f"focus-nav-{key_prefix}-play",
            use_container_width=True,
            on_click=toggle_guided_playback,
            args=(line_count,),
        )
    else:
        center_column.markdown(
            f"<div class='focus-position'>{current_index + 1} / {line_count}</div>",
            unsafe_allow_html=True,
        )
    next_column.button(
        "下一句",
        key=f"focus-nav-{key_prefix}-next",
        disabled=current_index >= line_count - 1,
        use_container_width=True,
        on_click=move_focus_line,
        args=(1, line_count),
    )
    if show_playback:
        st.markdown(
            f"<div class='focus-position'>{current_index + 1} / {line_count}</div>",
            unsafe_allow_html=True,
        )


@st.fragment(run_every=0.5)
def render_guided_mode(lines: list[dict[str, Any]]) -> None:
    """局部计时推进领读当前句，不触发整页重跑。"""
    now = time.monotonic()
    if st.session_state.is_playing:
        interval = SPEED_SECONDS[st.session_state.speed]
        if now - st.session_state.last_advance_at >= interval:
            next_index = bounded_line_index(
                st.session_state.current_line_index,
                1,
                len(lines),
            )
            if next_index == st.session_state.current_line_index:
                st.session_state.is_playing = False
            else:
                st.session_state.current_line_index = next_index
            st.session_state.last_advance_at = now

    st.segmented_control(
        "速度",
        options=list(SPEED_SECONDS),
        key="speed",
        on_change=reset_guided_clock,
    )
    render_focus_reader(lines, key_prefix="guided", show_playback=True)


def render_poem(poem: dict[str, Any]) -> None:
    """展示词作元数据，并按当前阅读模式渲染可点击正文。"""
    title = poem.get("title")
    heading = html.escape(poem.get("tune_name") or "未题词牌")
    if title:
        heading = f"{heading} <span class='poem-title'>· {html.escape(title)}</span>"
    meta = " · ".join(
        html.escape(str(value))
        for value in (poem.get("dynasty"), poem.get("author"), poem.get("musical_mode"))
        if value
    )
    st.markdown(
        f"<div class='poem-heading'><div class='poem-tune'>{heading}</div>"
        f"<div class='poem-meta'>{meta}</div></div>",
        unsafe_allow_html=True,
    )

    if poem.get("preface"):
        st.markdown(
            f"<div class='poem-preface'>{html.escape(poem['preface'])}</div>",
            unsafe_allow_html=True,
        )

    reading_mode = st.segmented_control(
        "阅读模式",
        options=list(READING_MODES),
        key="reading_mode",
        on_change=change_reading_mode,
    )
    lines = flatten_poem_lines(poem.get("sections", []))
    if reading_mode == "通读":
        render_overview_mode(poem)
    elif reading_mode == "慢读":
        render_slow_mode(poem)
    elif reading_mode == "转轮":
        render_focus_reader(lines, key_prefix="wheel", show_playback=False)
    else:
        render_guided_mode(lines)

    if poem.get("source"):
        st.caption(f"文本来源：{poem['source']}")


def render_allusion_evidence_preview(
    poem_id: str,
    candidates: list[dict[str, Any]],
) -> None:
    """展示 Reviewer 结论，并默认折叠原候选证据预览。"""
    if _all_candidates_have_no_evidence(candidates):
        st.info("所有候选均未查到外部候选证据；候选仍可用于手动查询。")

    for index, candidate in enumerate(candidates):
        anchor_text = str(candidate.get("anchor_text") or "未命名候选")
        review = candidate.get("review_result") or {}
        if review:
            overall_label = REVIEW_STATUS_LABELS.get(
                str(review.get("review_status") or ""),
                "状态未知",
            )
        else:
            overall_status = str(candidate.get("overall_status") or "")
            overall_label = _evidence_status_text(overall_status, overall=True)
        with st.expander(
            f"{anchor_text} · {overall_label}",
            expanded=index == 0,
        ):
            st.button(
                anchor_text,
                key=f"candidate-anchor-{poem_id}-{index}",
                help="填入下方选中文本",
                on_click=choose_line,
                args=_candidate_selection_payload(candidate),
            )
            st.caption(
                f"第 {candidate.get('line_no')} 句 · "
                f"{_candidate_type_label(str(candidate.get('candidate_type') or ''))} · "
                f"{candidate.get('confidence')}"
            )
            query_variants = candidate.get("query_variants") or []
            st.caption("查询变体：" + " · ".join(str(value) for value in query_variants))
            st.caption(str(candidate.get("reason") or ""))
            results = candidate.get("evidence_results") or []
            if review:
                st.markdown(_review_result_html(review), unsafe_allow_html=True)
                best = review.get("best_evidence") or []
                if best:
                    st.caption("最佳候选证据")
                    for item in best:
                        st.markdown(
                            _review_evidence_html(item),
                            unsafe_allow_html=True,
                        )
                secondary = [
                    *(review.get("downgraded_evidence") or []),
                    *(review.get("rejected_evidence") or []),
                ]
                if secondary:
                    with st.popover(f"查看降级与拒绝证据 · {len(secondary)}"):
                        for item in secondary:
                            st.markdown(
                                _review_evidence_html(item),
                                unsafe_allow_html=True,
                            )

            if results:
                with st.popover("查看原候选证据预览"):
                    for result in results:
                        st.markdown(
                            _evidence_preview_html(result),
                            unsafe_allow_html=True,
                        )
                long_entries = [
                    entry
                    for result in results
                    for entry in _long_evidence_entries(result)
                ]
                if long_entries:
                    with st.popover(f"查看候选证据长引文 · {len(long_entries)}"):
                        for title, full_text in long_entries:
                            st.caption(title)
                            st.text(full_text)
            elif not review:
                st.markdown(
                    "<div class='empty-state'>尚无候选证据结果</div>",
                    unsafe_allow_html=True,
                )


def render_evidences(items: list[dict[str, Any]]) -> None:
    if not items:
        st.markdown("<div class='empty-state'>暂无候选</div>", unsafe_allow_html=True)
        return
    for item in items:
        st.markdown(
            _card_html(
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
    if not items:
        st.markdown("<div class='empty-state'>暂无候选</div>", unsafe_allow_html=True)
        return
    for item in items:
        st.markdown(
            _card_html(
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


def render_reading_results(
    data: dict[str, Any] | None,
    included_tools: list[str] | None,
) -> None:
    """按工具类型展示窄模型字段，忽略 raw。"""
    if not data:
        st.markdown("<div class='empty-state'>尚未查询</div>", unsafe_allow_html=True)
        return

    evidences = data.get("evidences", [])
    by_tool = {
        tool_name: [item for item in evidences if item.get("tool_name") == tool_name]
        for tool_name in ("char", "reference", "ci_tune")
    }
    rhyme_items = (data.get("prosody") or {}).get("rhyme_info", [])
    allusions = data.get("allusions", [])
    errors_by_tool = _group_tool_errors(data.get("errors", []))
    included = set(included_tools or TOOL_LABELS)

    result_count = len(evidences) + len(rhyme_items) + len(allusions)
    hard_error_tools = {
        tool_name
        for tool_name, errors in errors_by_tool.items()
        if any("HTTP 404" not in error for error in errors)
    }
    if included and result_count == 0 and included.issubset(hard_error_tools):
        st.error("本次所选工具均暂时不可用，正文仍可继续阅读。")

    tabs = st.tabs(["字词释义", "典故候选", "出处与化用", "韵部", "词谱 / 平仄"])
    with tabs[0]:
        if "char" not in included:
            st.markdown("<div class='empty-state'>本次未查询</div>", unsafe_allow_html=True)
        else:
            render_tool_status("char", errors_by_tool.get("char", []), bool(by_tool["char"]))
            render_evidences(by_tool["char"])
    with tabs[1]:
        if "allusion" not in included:
            st.markdown("<div class='empty-state'>本次未查询</div>", unsafe_allow_html=True)
        else:
            render_tool_status("allusion", errors_by_tool.get("allusion", []), bool(allusions))
            render_allusions(allusions)
    with tabs[2]:
        if "reference" not in included:
            st.markdown("<div class='empty-state'>本次未查询</div>", unsafe_allow_html=True)
        else:
            render_tool_status(
                "reference",
                errors_by_tool.get("reference", []),
                bool(by_tool["reference"]),
            )
            render_evidences(by_tool["reference"])
    with tabs[3]:
        if "rhyme" not in included:
            st.markdown("<div class='empty-state'>本次未查询</div>", unsafe_allow_html=True)
        else:
            render_tool_status("rhyme", errors_by_tool.get("rhyme", []), bool(rhyme_items))
            render_evidences(rhyme_items)
    with tabs[4]:
        if "ci_tune" not in included:
            st.markdown("<div class='empty-state'>本次未查询</div>", unsafe_allow_html=True)
        else:
            render_tool_status(
                "ci_tune",
                errors_by_tool.get("ci_tune", []),
                bool(by_tool["ci_tune"]),
            )
            render_evidences(by_tool["ci_tune"])


def render_tools(poem: dict[str, Any]) -> None:
    """展示 AI 候选入口、手动工具表单和证据结果。"""
    st.markdown("### 阅读辅助")
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

    candidates = _allusion_candidate_items(st.session_state.allusion_candidates)
    if st.session_state.allusion_candidates is not None and not candidates:
        st.markdown(
            "<div class='empty-state'>本词暂未识别到明确的典故候选</div>",
            unsafe_allow_html=True,
        )
    elif candidates:
        candidate_options = [str(index) for index in range(len(candidates))]
        st.pills(
            "候选锚点",
            options=candidate_options,
            key="allusion_candidate_selection",
            format_func=lambda index: candidates[int(index)]["anchor_text"],
            on_change=choose_allusion_candidate,
        )
        selected_candidate = st.session_state.get("allusion_candidate_selection")
        if selected_candidate is not None:
            candidate = candidates[int(selected_candidate)]
            st.caption(
                f"第 {candidate['line_no']} 句 · "
                f"{_candidate_type_label(str(candidate['candidate_type']))} · "
                f"{candidate['confidence']}：{candidate['reason']}"
            )
        render_allusion_evidence_preview(poem["poem_id"], candidates)

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
        normalized_text = selected_text.strip()
        if not normalized_text:
            st.warning("请输入或选择文本")
        elif not selected_labels:
            st.warning("请至少选择一个工具")
        else:
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

    render_reading_results(
        st.session_state.get("reading_aids"),
        st.session_state.get("last_included_tools"),
    )
    st.markdown(
        "<div class='future-slot'><strong>AI 综合解释</strong><br>下一版本接入</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="清商 Reader",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme_name = st.sidebar.segmented_control(
        "外观",
        options=list(THEME_PALETTES),
        default="浅色",
        key="reader_theme",
    )
    install_styles(theme_name or "浅色")

    try:
        poems = fetch_poems()
    except ReaderAPIError as exc:
        render_hero()
        st.error(str(exc))
        return

    if not poems:
        render_hero()
        st.warning("当前没有可读的周邦彦词作")
        return

    initialize_state(poems)
    render_poem_directory(poems)
    render_hero()

    try:
        poem = fetch_poem(st.session_state.poem_id)
    except ReaderAPIError as exc:
        st.error(str(exc))
        return

    poem_column, tools_column = st.columns([1.2, 1], gap="large")
    with poem_column:
        render_poem(poem)
    with tools_column:
        render_tools(poem)


if __name__ == "__main__":
    main()
