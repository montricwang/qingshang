"""Reader 左侧词作正文与阅读模式。"""

from __future__ import annotations

import html
import time
from typing import Any

import streamlit as st

from apps.reader.config import READING_MODES, SPEED_SECONDS
from apps.reader.state import (
    change_reading_mode,
    choose_line,
    move_focus_line,
    reset_guided_clock,
    toggle_guided_playback,
)
from apps.reader.text import (
    bounded_line_index,
    build_breathing_fragments,
    flatten_poem_lines,
)


def render_section_break(section_index: int) -> None:
    """在片段之间加入视觉分隔。"""
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


def _render_focus_line(
    lines: list[dict[str, Any]],
    current_index: int,
    key_prefix: str,
) -> None:
    """以低透明度上下文 + 当前句按钮展示单行聚焦视图。"""
    current_line = lines[current_index]
    previous_text = lines[current_index - 1]["text"] if current_index else ""
    next_text = lines[current_index + 1]["text"] if current_index + 1 < len(lines) else ""

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


def _render_focus_controls(
    *,
    current_index: int,
    line_count: int,
    key_prefix: str,
    show_playback: bool,
) -> None:
    """渲染转轮/领读导航按钮：上一句、播放/暂停/计数、下一句。"""
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

    _render_focus_line(lines, current_index, key_prefix)
    _render_focus_controls(
        current_index=current_index,
        line_count=line_count,
        key_prefix=key_prefix,
        show_playback=show_playback,
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
