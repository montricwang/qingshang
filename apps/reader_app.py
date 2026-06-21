"""清商 Reader v0.1.5：本地词作阅读与手动 CNKGraph 辅助。"""

from __future__ import annotations

import base64
import html
import os
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HERO_IMAGE = PROJECT_ROOT / "apps/assets/reader-landscape.webp"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 45.0
DIRECTORY_PAGE_SIZE = 24

TOOL_LABELS = {
    "allusion": "典故候选",
    "reference": "出处与化用",
    "char": "字词释义",
    "rhyme": "韵部",
    "ci_tune": "词谱 / 平仄",
}


class ReaderAPIError(RuntimeError):
    """表示 Reader 无法从本地 FastAPI 获得有效数据。"""


def _api_url(path: str) -> str:
    base_url = os.getenv("QINGSHANG_API_BASE_URL", DEFAULT_API_BASE_URL)
    return f"{base_url.rstrip('/')}{path}"


def _response_json(response: httpx.Response) -> Any:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = response.text
        raise ReaderAPIError(detail or f"本地 API 返回 HTTP {response.status_code}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise ReaderAPIError("本地 API 返回的内容不是有效 JSON") from exc


@st.cache_data(ttl=30, show_spinner=False)
def fetch_poems() -> list[dict[str, Any]]:
    """读取周邦彦词作目录。"""
    try:
        response = httpx.get(
            _api_url("/api/poems"),
            params={"author": "周邦彦", "limit": 500},
            timeout=API_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise ReaderAPIError("无法连接清商 FastAPI") from exc
    data = _response_json(response)
    return data if isinstance(data, list) else []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_poem(poem_id: str) -> dict[str, Any]:
    """读取一首词的完整结构。"""
    try:
        response = httpx.get(
            _api_url(f"/api/poems/{poem_id}"),
            timeout=API_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise ReaderAPIError("无法读取词作详情") from exc
    data = _response_json(response)
    return data if isinstance(data, dict) else {}


def fetch_reading_aids(
    poem_id: str,
    selected_text: str,
    line_no: int | None,
    include: list[str],
) -> dict[str, Any]:
    """手动请求当前词作的阅读辅助证据。"""
    payload = {
        "selected_text": selected_text,
        "line_no": line_no,
        "include": include,
    }
    try:
        response = httpx.post(
            _api_url(f"/api/poems/{poem_id}/reading-aids"),
            json=payload,
            timeout=API_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise ReaderAPIError("阅读辅助请求失败，正文仍可继续阅读") from exc
    data = _response_json(response)
    return data if isinstance(data, dict) else {}


def install_styles() -> None:
    """应用 Reader 的稳定布局和领域视觉样式。"""
    st.markdown(
        """
        <style>
        .stApp { background: #f7f8f6; color: #202824; }
        [data-testid="stSidebar"] {
            background: #e9eeeb;
            border-right: 1px solid #c9d1cd;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button {
            min-height: 2.7rem;
            text-align: left;
            justify-content: flex-start;
            border-radius: 4px;
            letter-spacing: 0;
        }
        .block-container {
            max-width: 1480px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }
        .reader-hero {
            height: 148px;
            background-size: cover;
            background-position: center;
            border: 1px solid #c9c1ae;
            border-radius: 6px;
            margin-bottom: 1.2rem;
            padding: 28px 36px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .reader-brand {
            color: #26332d;
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            font-size: 2.25rem;
            font-weight: 700;
            line-height: 1.1;
            letter-spacing: 0;
        }
        .reader-version {
            color: #6c5147;
            font-size: 0.8rem;
            margin-top: 0.55rem;
            letter-spacing: 0;
        }
        .poem-heading {
            border-bottom: 1px solid #cbd2ce;
            padding: 0.25rem 0 1rem;
            margin-bottom: 1.2rem;
        }
        .poem-tune {
            color: #202824;
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            font-size: 1.75rem;
            font-weight: 700;
            line-height: 1.25;
            letter-spacing: 0;
        }
        .poem-meta { color: #6b746f; font-size: 0.9rem; margin-top: 0.45rem; }
        .poem-preface {
            color: #535e58;
            font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
            line-height: 1.9;
            padding: 0.7rem 0;
        }
        .section-label {
            color: #7e3430;
            font-size: 0.78rem;
            font-weight: 700;
            margin: 1.1rem 0 0.4rem;
            letter-spacing: 0;
        }
        .evidence-card {
            background: #ffffff;
            border: 1px solid #cdd5d1;
            border-left: 3px solid #54766a;
            border-radius: 5px;
            padding: 0.85rem 0.95rem;
            margin: 0.55rem 0;
            overflow-wrap: anywhere;
        }
        .evidence-anchor { color: #8a3832; font-size: 0.78rem; font-weight: 700; }
        .evidence-title { color: #202824; font-weight: 700; margin: 0.25rem 0; }
        .evidence-body { color: #39443f; font-size: 0.9rem; line-height: 1.65; }
        .evidence-source {
            color: #76817b;
            border-top: 1px solid #e3e7e5;
            font-size: 0.75rem;
            margin-top: 0.6rem;
            padding-top: 0.5rem;
        }
        .empty-state {
            color: #78827d;
            border: 1px dashed #c7cfcb;
            border-radius: 5px;
            padding: 0.9rem;
            margin: 0.5rem 0;
        }
        .future-slot {
            background: #eef1ef;
            border: 1px solid #d0d7d3;
            border-radius: 5px;
            color: #626d67;
            padding: 0.75rem 0.85rem;
            margin-top: 0.65rem;
            font-size: 0.83rem;
        }
        .future-slot strong { color: #39453f; }
        [data-testid="stForm"] { border-radius: 6px; border-color: #c9d1cd; }
        [data-testid="stTabs"] button { letter-spacing: 0; }
        [data-testid="stButton"] button { border-radius: 4px; letter-spacing: 0; }
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
            <div class="reader-version">Reader v0.1.5 · 周邦彦词作</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _poem_label(poem: dict[str, Any]) -> str:
    title = poem.get("title")
    tune_name = poem.get("tune_name") or "未题词牌"
    return f"{tune_name} · {title}" if title else tune_name


def choose_poem(poem_id: str) -> None:
    """切换作品时清空上一首词的选句和证据。"""
    st.session_state.poem_id = poem_id
    st.session_state.selected_text = ""
    st.session_state.selected_line_no = None
    st.session_state.selected_line_text = None
    st.session_state.reading_aids = None


def choose_line(line_no: int, text: str) -> None:
    """把点击的词句同步到右侧查询框。"""
    st.session_state.selected_text = text
    st.session_state.selected_line_no = line_no
    st.session_state.selected_line_text = text
    st.session_state.reading_aids = None


def reset_directory_page() -> None:
    st.session_state.directory_page = 0


def change_directory_page(delta: int) -> None:
    st.session_state.directory_page += delta


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


def render_poem(poem: dict[str, Any]) -> None:
    """展示词作元数据、题序、分片和可点击词句。"""
    title = poem.get("title")
    heading = html.escape(poem.get("tune_name") or "未题词牌")
    if title:
        heading = f"{heading} <span style='color:#6f7773;font-weight:400'>· {html.escape(title)}</span>"
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

    for section in poem.get("sections", []):
        section_name = section.get("section_name") or f"第 {section.get('section_no')} 片"
        st.markdown(
            f"<div class='section-label'>{html.escape(str(section_name))}</div>",
            unsafe_allow_html=True,
        )
        for line in section.get("lines", []):
            line_no = line["global_line_no"]
            line_text = line["text"]
            selected = line_no == st.session_state.selected_line_no
            st.button(
                f"{line_no:02d}　{line_text}",
                key=f"line-{poem['poem_id']}-{line_no}",
                type="primary" if selected else "secondary",
                use_container_width=True,
                on_click=choose_line,
                args=(line_no, line_text),
            )

    if poem.get("source"):
        st.caption(f"文本来源：{poem['source']}")


def _card_html(
    *,
    anchor_text: str | None,
    title: str | None,
    body: str | None,
    detail: str | None,
    source_ref: str | None,
    source: str = "cnkgraph",
) -> str:
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


def render_reading_results(data: dict[str, Any] | None) -> None:
    """按工具类型展示窄模型字段，忽略 raw。"""
    if not data:
        st.markdown("<div class='empty-state'>尚未查询</div>", unsafe_allow_html=True)
        return

    for error in data.get("errors", []):
        st.warning(error)

    evidences = data.get("evidences", [])
    by_tool = {
        tool_name: [item for item in evidences if item.get("tool_name") == tool_name]
        for tool_name in ("char", "reference", "ci_tune")
    }
    rhyme_items = (data.get("prosody") or {}).get("rhyme_info", [])

    tabs = st.tabs(["字词释义", "典故候选", "出处与化用", "韵部", "词谱 / 平仄"])
    with tabs[0]:
        render_evidences(by_tool["char"])
    with tabs[1]:
        render_allusions(data.get("allusions", []))
    with tabs[2]:
        render_evidences(by_tool["reference"])
    with tabs[3]:
        render_evidences(rhyme_items)
    with tabs[4]:
        render_evidences(by_tool["ci_tune"])


def render_tools(poem: dict[str, Any]) -> None:
    """展示手动工具表单、结果分区和下一版本占位区。"""
    st.markdown("### 阅读辅助")
    with st.form("reading-aids-form", border=True):
        selected_text = st.text_input(
            "选中文本",
            key="selected_text",
            placeholder="兔葵燕麦",
        )
        selected_labels = st.multiselect(
            "工具",
            options=list(TOOL_LABELS),
            default=list(TOOL_LABELS),
            format_func=lambda key: TOOL_LABELS[key],
        )
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
            try:
                with st.spinner("正在查询外部证据"):
                    st.session_state.reading_aids = fetch_reading_aids(
                        poem["poem_id"],
                        normalized_text,
                        line_no,
                        selected_labels,
                    )
            except ReaderAPIError as exc:
                st.error(str(exc))

    render_reading_results(st.session_state.get("reading_aids"))
    st.markdown(
        "<div class='future-slot'><strong>AI 自动识别候选</strong><br>下一版本接入</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='future-slot'><strong>AI 综合解释</strong><br>下一版本接入</div>",
        unsafe_allow_html=True,
    )


def initialize_state(poems: list[dict[str, Any]]) -> None:
    if "poem_id" not in st.session_state:
        st.session_state.poem_id = poems[0]["poem_id"] if poems else None
    st.session_state.setdefault("selected_text", "")
    st.session_state.setdefault("selected_line_no", None)
    st.session_state.setdefault("selected_line_text", None)
    st.session_state.setdefault("reading_aids", None)
    st.session_state.setdefault("directory_page", 0)


def main() -> None:
    st.set_page_config(
        page_title="清商 Reader",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    install_styles()

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
