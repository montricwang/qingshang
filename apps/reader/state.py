"""Reader 的 Streamlit session_state 回调。

Streamlit 会在用户点击按钮、切换控件或页面 rerun 时保留 session_state。
这里集中管理这些状态变化，避免回调散落在页面渲染代码中。
"""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from apps.reader.config import SPEED_SECONDS
from apps.reader.text import bounded_line_index


# ---------------------------------------------------------------------------
# 词作切换
# ---------------------------------------------------------------------------


def choose_poem(poem_id: str) -> None:
    """切换当前词作，并清空依赖上一首词的阅读状态。"""
    st.session_state.poem_id = poem_id
    st.session_state.selected_text = ""
    st.session_state.selected_line_no = None
    st.session_state.selected_line_text = None
    st.session_state.reading_aids = None
    st.session_state.last_included_tools = None
    st.session_state.allusion_candidates = None
    st.session_state.allusion_candidate_error = None
    st.session_state.allusion_candidate_selection = None
    st.session_state.current_line_index = 0
    st.session_state.is_playing = False


# ---------------------------------------------------------------------------
# 文本选择
# ---------------------------------------------------------------------------


def choose_line(line_no: int, text: str) -> None:
    """把正文中点击的句子或候选锚点回填到右侧查询框。"""
    st.session_state.selected_text = text
    st.session_state.selected_line_no = line_no
    st.session_state.selected_line_text = text
    st.session_state.reading_aids = None
    st.session_state.last_included_tools = None


# ---------------------------------------------------------------------------
# 候选选择与回填
# ---------------------------------------------------------------------------


def allusion_candidate_items(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """兼容候选接口不同阶段的 items/candidates 字段名。"""
    if not data:
        return []
    items = data.get("items")
    if isinstance(items, list):
        return items
    candidates = data.get("candidates")
    return candidates if isinstance(candidates, list) else []


def candidate_selection_payload(candidate: dict[str, Any]) -> tuple[int, str]:
    """候选按钮只回填原文 anchor，不回填 query_variants。"""
    return int(candidate["line_no"]), str(candidate["anchor_text"])


def choose_allusion_candidate() -> None:
    """根据 pills 选择，把候选 anchor 回填到 selected_text。"""
    candidates = allusion_candidate_items(st.session_state.get("allusion_candidates"))
    selected = st.session_state.get("allusion_candidate_selection")
    if selected is None or not candidates:
        return
    candidate = candidates[int(selected)]
    choose_line(*candidate_selection_payload(candidate))


# ---------------------------------------------------------------------------
# 阅读模式控制
# ---------------------------------------------------------------------------


def change_reading_mode() -> None:
    """切换阅读模式时停止领读，避免后台自动推进继续运行。"""
    st.session_state.is_playing = False
    st.session_state.last_advance_at = time.monotonic()


# ---------------------------------------------------------------------------
# 领读控制（转轮模式自动推进）
# ---------------------------------------------------------------------------


def move_focus_line(delta: int, line_count: int) -> None:
    """转轮/领读模式中移动当前句。"""
    st.session_state.current_line_index = bounded_line_index(
        st.session_state.current_line_index,
        delta,
        line_count,
    )
    st.session_state.last_advance_at = time.monotonic()


def toggle_guided_playback(line_count: int) -> None:
    """开启或暂停领读模式的自动推进。"""
    if line_count <= 0:
        return
    if st.session_state.current_line_index >= line_count - 1:
        st.session_state.current_line_index = 0
    st.session_state.is_playing = not st.session_state.is_playing
    st.session_state.last_advance_at = time.monotonic()


def reset_guided_clock() -> None:
    """速度切换后重置计时起点。"""
    st.session_state.last_advance_at = time.monotonic()


def maybe_advance_guided_line(line_count: int) -> None:
    """领读模式按速度设置推进一句。

    Streamlit 会定时重跑 fragment；这个函数只根据 session_state 判断是否推进。
    """
    if not st.session_state.get("is_playing") or line_count <= 0:
        return
    speed = st.session_state.get("speed", "中")
    interval = SPEED_SECONDS.get(speed, 4.0)
    now = time.monotonic()
    if now - st.session_state.last_advance_at < interval:
        return
    next_index = st.session_state.current_line_index + 1
    if next_index >= line_count:
        st.session_state.is_playing = False
        st.session_state.current_line_index = line_count - 1
    else:
        st.session_state.current_line_index = next_index
    st.session_state.last_advance_at = now


# ---------------------------------------------------------------------------
# 目录翻页
# ---------------------------------------------------------------------------


def reset_directory_page() -> None:
    """目录筛选变化后回到第一页。"""
    st.session_state.directory_page = 0


def change_directory_page(delta: int) -> None:
    """目录按钮翻页；页面渲染阶段会再次夹住合法范围。"""
    st.session_state.directory_page += delta


# ---------------------------------------------------------------------------
# 页面初始化
# ---------------------------------------------------------------------------


def initialize_state(poems: list[dict[str, Any]]) -> None:
    """初始化 Reader 页面需要跨 rerun 保存的状态。"""
    if "poem_id" not in st.session_state:
        st.session_state.poem_id = poems[0]["poem_id"] if poems else None
    st.session_state.setdefault("selected_text", "")
    st.session_state.setdefault("selected_line_no", None)
    st.session_state.setdefault("selected_line_text", None)
    st.session_state.setdefault("reading_aids", None)
    st.session_state.setdefault("last_included_tools", None)
    st.session_state.setdefault("allusion_candidates", None)
    st.session_state.setdefault("allusion_candidate_error", None)
    st.session_state.setdefault("directory_page", 0)
    st.session_state.setdefault("reading_mode", "慢读")
    st.session_state.setdefault("current_line_index", 0)
    st.session_state.setdefault("is_playing", False)
    st.session_state.setdefault("speed", "中")
    st.session_state.setdefault("last_advance_at", time.monotonic())
