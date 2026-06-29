"""Reader 侧栏词作目录。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from apps.reader.api_client import fetch_opening_lines
from apps.reader.config import DIRECTORY_PAGE_SIZE
from apps.reader.state import change_directory_page, choose_poem, reset_directory_page
from apps.reader.text import strip_trailing_pause


def _poem_label(poem: dict[str, Any]) -> str:
    """生成目录按钮使用的词作标题。"""
    title = poem.get("title")
    tune_name = poem.get("tune_name") or "未题词牌"
    series_label = poem.get("series_label")
    suffix = " · ".join(value for value in (title, series_label) if value)
    return f"{tune_name} · {suffix}" if suffix else tune_name


def _filter_directory_poems(
    poems: list[dict[str, Any]],
    query: str,
) -> tuple[list[dict[str, Any]], int, int, int, dict[str, str]]:
    """按筛选文本过滤词作并计算分页信息。"""
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
    return visible_poems, page_count, page, len(filtered), opening_lines


def render_poem_directory(poems: list[dict[str, Any]]) -> None:
    """在侧栏展示可筛选的周邦彦词作目录。"""
    st.sidebar.markdown("## 词作目录")
    query = st.sidebar.text_input(
        "筛选",
        placeholder="词牌或题名",
        key="directory_query",
        on_change=reset_directory_page,
    )
    visible_poems, page_count, page, total_count, opening_lines = _filter_directory_poems(
        poems,
        query,
    )

    st.sidebar.caption(f"{total_count} 首 · 第 {page + 1}/{page_count} 页")
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
            st.sidebar.caption(strip_trailing_pause(opening_lines[poem_id]))
