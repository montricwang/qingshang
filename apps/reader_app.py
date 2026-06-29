"""清商 Reader v0.2.0：本地词作阅读与候选证据审阅短注。"""

from __future__ import annotations

import base64

import streamlit as st

from apps.reader.api_client import ReaderAPIError, fetch_poem, fetch_poems
from apps.reader.config import HERO_IMAGE, READER_CSS, THEME_PALETTES
from apps.reader.directory import render_poem_directory
from apps.reader.poem_view import render_poem
from apps.reader.state import initialize_state
from apps.reader.tools_panel import render_tools


def install_styles(theme_name: str) -> None:
    """应用 Reader 的稳定布局和领域视觉样式。"""
    palette = THEME_PALETTES[theme_name]
    variables = "\n".join(
        f"--qs-{name.replace('_', '-')}: {value};" for name, value in palette.items()
    )
    css = READER_CSS.read_text(encoding="utf-8")
    st.markdown(
        f"<style>:root {{ {variables} }}\n{css}</style>",
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


def main() -> None:
    """装配 Reader 页面：取目录、取当前词作、交给子模块渲染。"""
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
