"""清商 Reader v0.2.0-preview：可观察的 Evidence Review Workflow。"""

from __future__ import annotations

import base64
import html
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypedDict

import httpx
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HERO_IMAGE = PROJECT_ROOT / "apps/assets/reader-landscape.webp"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 45.0
REVIEW_TIMEOUT_SECONDS = float(os.getenv("QINGSHANG_REVIEW_TIMEOUT_SECONDS", "180"))
DIRECTORY_PAGE_SIZE = 24
TRAILING_PAUSE_PATTERN = re.compile(r"[，。！？；、：]+$")
SOFT_STOPS = {"，", "、"}
HARD_STOPS = {"。", "！", "？", "；", "："}
BREATHING_STOPS = SOFT_STOPS | HARD_STOPS
CLOSING_MARKS = {"”", "’", "」", "』", "》", "）", "】"}
FULL_WIDTH_INDENT = "　　"
READING_MODES = ("通读", "慢读", "转轮", "领读")
SPEED_SECONDS = {"快": 2.5, "中": 4.0, "慢": 6.0}

TOOL_LABELS = {
    "allusion": "典故候选",
    "reference": "出处与化用",
    "char": "字词释义",
    "rhyme": "韵部",
    "ci_tune": "词谱 / 平仄",
}

EVIDENCE_SOURCE_LABELS = {
    "cnkgraph_allusion": "CNKGraph 典故候选",
    "cnkgraph_reference": "CNKGraph 出处与化用",
}
EVIDENCE_STATUS_LABELS = {
    "hit": "命中候选证据",
    "no_result": "无结果",
    "error": "查询错误",
}
OVERALL_STATUS_LABELS = {
    "hit": "查到候选证据",
    "no_result": "未查到候选证据",
    "partial_error": "候选证据部分查询失败",
    "error": "候选证据查询失败",
}
CANDIDATE_TYPE_LABELS = {
    "allusion": "典故",
    "literary_reference": "文献化用",
    "historical_place": "历史地名",
    "cultural_institution": "礼俗制度",
    "conventional_motif": "惯用母题",
    "uncertain": "待查",
}
EVIDENCE_CONTEXT_LABELS = {
    "prior_source": "前代来源候选",
    "current_poem": "当前作品命中",
    "later_usage": "后代用例",
}
REVIEW_STATUS_LABELS = {
    "reviewed": "已生成审阅短注",
    "insufficient_evidence": "证据不足",
    "ambiguous": "证据有歧义",
    "error": "审阅失败",
}
REVIEW_ROLE_LABELS = {
    "prior_source": "前代来源",
    "current_work_self_hit": "当前作品自命中",
    "later_reuse": "后代沿用",
    "weak_related": "弱相关",
    "irrelevant": "无关或误命中",
    "unknown": "关系不明",
}
WORKFLOW_STATUS_LABELS = {
    "pending": "等待",
    "running": "运行中",
    "done": "完成",
    "error": "失败",
}
EVIDENCE_EXCERPT_LIMIT = 160

THEME_PALETTES = {
    "浅色": {
        "app_bg": "#f5f4f0",
        "sidebar_bg": "#e8ebe7",
        "surface": "#fbfbf8",
        "surface_muted": "#eeefeb",
        "text": "#27302c",
        "text_muted": "#69716c",
        "border": "#c9cfca",
        "border_soft": "#dde1dd",
        "accent": "#85554a",
        "accent_hover": "#72483f",
        "accent_soft": "#eaded9",
        "green": "#526d62",
        "hero_tint": "#f5f4f0",
        "hero_blend": "normal",
    },
    "深色": {
        "app_bg": "#1d2421",
        "sidebar_bg": "#242c28",
        "surface": "#29312d",
        "surface_muted": "#313934",
        "text": "#e7e4dc",
        "text_muted": "#aab1ac",
        "border": "#4b5650",
        "border_soft": "#3a443f",
        "accent": "#bd8b7e",
        "accent_hover": "#c99a8d",
        "accent_soft": "#493a35",
        "green": "#8ca99d",
        "hero_tint": "#354039",
        "hero_blend": "multiply",
    },
}


class ReaderAPIError(RuntimeError):
    """表示 Reader 无法从本地 FastAPI 获得有效数据。"""


def _config_value(name: str, default: str = "") -> str:
    """优先读取环境变量，再读取 Streamlit Cloud secrets。"""
    value = os.getenv(name)
    if value is not None:
        return value

    secret_paths = (
        Path.home() / ".streamlit" / "secrets.toml",
        PROJECT_ROOT / ".streamlit" / "secrets.toml",
    )
    if not any(path.exists() for path in secret_paths):
        return default

    try:
        secret = st.secrets.get(name, default)
    except Exception:
        # secrets 文件无效时仍使用本地默认值，让正文保持可读。
        return default
    return str(secret)


def _public_demo_mode() -> bool:
    return _config_value("PUBLIC_DEMO_MODE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _demo_poems() -> list[dict[str, Any]]:
    return [
        {
            "poem_id": "demo-nandu-shidai",
            "author": "周邦彦",
            "dynasty": "宋",
            "tune_name": "少年游",
            "title": None,
            "series_label": "示例",
        }
    ]


def _demo_poem_detail() -> dict[str, Any]:
    return {
        **_demo_poems()[0],
        "preface": None,
        "source": "Public Demo Mode 内置样例文本",
        "sections": [
            {
                "section_no": 1,
                "section_name": "全篇",
                "lines": [
                    {
                        "global_line_no": 1,
                        "section_line_no": 1,
                        "text": "南都石黛扫晴山。",
                    },
                    {
                        "global_line_no": 2,
                        "section_line_no": 2,
                        "text": "衣薄耐朝寒。",
                    },
                ],
            }
        ],
    }


def _demo_workflow_result(selected_text: str, line_no: int | None) -> dict[str, Any]:
    """在公共部署没有后端依赖时提供清楚标记的固定样例。"""
    review = {
        "review_status": "reviewed",
        "confidence": "high",
        "short_note": "候选证据显示，“石黛”可指画眉颜料；此处将“晴山”联系眉黛，是一种有文献依据但仍需人工确认的读法。",
        "best_evidence": [
            {
                "evidence_id": "sample-e1",
                "source": "cnkgraph_reference",
                "query_used": "南都石黛",
                "title": "玉台新咏序",
                "source_ref": "南朝 徐陵 《玉台新咏序》",
                "role": "prior_source",
                "relevance": "strong",
                "reason": "内置样例中的前代文献候选与“南都石黛”原文短语可直接比对。",
            }
        ],
        "downgraded_evidence": [],
        "rejected_evidence": [],
        "caveat": "Public Demo Mode sample data，不代表实时 CNKGraph 或 LLM 结果。",
    }
    candidate = {
        "line_no": 1,
        "line_text": "南都石黛扫晴山。",
        "anchor_text": "南都石黛",
        "candidate_type": "literary_reference",
        "query": "南都石黛",
        "query_variants": ["南都石黛", "徐陵 玉台新咏序 石黛"],
        "reason": "该原文短语可能涉及前代文献语词、成句或诗文化用，值得进一步查证。",
        "confidence": "high",
        "evidence_results": [],
        "overall_status": "hit",
        "review_result": review,
    }
    return {
        "poem_id": "demo-nandu-shidai",
        "line_no": line_no or 1,
        "selected_text": selected_text or "南都石黛扫晴山。",
        "intent": "allusion_or_reference_explanation",
        "candidates": [candidate],
        "workflow_trace": [
            {
                "step_name": "intent_router",
                "status": "done",
                "tool_name": "rule_router",
                "latency_ms": 1,
                "input_summary": selected_text or "南都石黛扫晴山。",
                "output_summary": "allusion_or_reference_explanation",
                "error": None,
            },
            {
                "step_name": "candidate_extraction",
                "status": "done",
                "tool_name": "sample_candidate_extractor",
                "latency_ms": 2,
                "input_summary": "Public Demo Mode sample data",
                "output_summary": "保留 1 个句级候选",
                "error": None,
            },
            {
                "step_name": "evidence_retrieval",
                "status": "done",
                "tool_name": "sample_cnkgraph",
                "latency_ms": 2,
                "input_summary": "1 个候选",
                "output_summary": "获得 1 条内置候选证据",
                "error": None,
            },
            {
                "step_name": "evidence_review",
                "status": "done",
                "tool_name": "sample_evidence_reviewer",
                "latency_ms": 2,
                "input_summary": "1 个候选证据包",
                "output_summary": "完成 1 个审阅",
                "error": None,
            },
            {
                "step_name": "final_answer",
                "status": "done",
                "tool_name": "deterministic_aggregator",
                "latency_ms": 1,
                "input_summary": "1 个 Review 结果",
                "output_summary": "已生成 sample 审阅短注",
                "error": None,
            },
        ],
        "final_answer": review["short_note"] + " 本页为 sample data。",
        "errors": [],
        "sample_data": True,
    }


class BreathingFragment(TypedDict):
    """一段可点击的慢读文本及其原始词句定位。"""

    line_no: int
    fragment_no: int
    text: str
    display_text: str
    indent_level: int
    source_line_text: str


def _api_url(path: str) -> str:
    base_url = _config_value("QINGSHANG_API_BASE_URL", DEFAULT_API_BASE_URL)
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
    if _public_demo_mode():
        return _demo_poems()
    try:
        response = httpx.get(
            _api_url("/api/poems"),
            params={"author": "周邦彦", "limit": 500},
            timeout=API_TIMEOUT_SECONDS,
            trust_env=False,
        )
        data = _response_json(response)
    except (httpx.RequestError, ReaderAPIError) as exc:
        if _public_demo_mode():
            return _demo_poems()
        raise ReaderAPIError("无法连接清商 FastAPI") from exc
    return data if isinstance(data, list) else []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_poem(poem_id: str) -> dict[str, Any]:
    """读取一首词的完整结构。"""
    if _public_demo_mode() and poem_id == "demo-nandu-shidai":
        return _demo_poem_detail()
    try:
        response = httpx.get(
            _api_url(f"/api/poems/{poem_id}"),
            timeout=API_TIMEOUT_SECONDS,
            trust_env=False,
        )
        data = _response_json(response)
    except (httpx.RequestError, ReaderAPIError) as exc:
        if _public_demo_mode() and poem_id == "demo-nandu-shidai":
            return _demo_poem_detail()
        raise ReaderAPIError("无法读取词作详情") from exc
    return data if isinstance(data, dict) else {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_opening_lines(poem_ids: tuple[str, ...]) -> dict[str, str]:
    """并发读取当前目录页无标题词作的起句，不改变列表接口。"""
    if _public_demo_mode() and poem_ids == ("demo-nandu-shidai",):
        return {"demo-nandu-shidai": "南都石黛扫晴山。"}

    def fetch_one(poem_id: str) -> tuple[str, str | None]:
        try:
            response = httpx.get(
                _api_url(f"/api/poems/{poem_id}"),
                timeout=API_TIMEOUT_SECONDS,
                trust_env=False,
            )
            data = _response_json(response)
        except (httpx.RequestError, ReaderAPIError):
            return poem_id, None

        sections = data.get("sections", []) if isinstance(data, dict) else []
        lines = sections[0].get("lines", []) if sections else []
        opening = lines[0].get("text") if lines else None
        return poem_id, opening

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(fetch_one, poem_ids)
    return {poem_id: opening for poem_id, opening in results if opening}


def _strip_trailing_pause(text: str) -> str:
    """只移除起句末尾连续出现的中文停顿标点。"""
    return TRAILING_PAUSE_PATTERN.sub("", text)


def build_breathing_fragments(
    sections: list[dict[str, Any]],
) -> list[list[BreathingFragment]]:
    """按句读拆出慢读分片，并在每个 section 内维护视觉缩进。"""
    section_fragments: list[list[BreathingFragment]] = []

    for section in sections:
        indent_level = 0
        fragments: list[BreathingFragment] = []

        for line in section.get("lines", []):
            line_no = line["global_line_no"]
            source_line_text = line["text"]
            buffer = ""
            fragment_no = 0
            pending_stop: str | None = None

            for char_index, char in enumerate(source_line_text):
                buffer += char
                next_char = (
                    source_line_text[char_index + 1]
                    if char_index + 1 < len(source_line_text)
                    else None
                )
                if char in BREATHING_STOPS:
                    pending_stop = char
                is_fragment_end = bool(
                    pending_stop
                    and (
                        char in BREATHING_STOPS
                        and next_char not in BREATHING_STOPS | CLOSING_MARKS
                        or char in CLOSING_MARKS
                        and next_char not in CLOSING_MARKS
                    )
                )
                if not is_fragment_end:
                    continue

                fragment_no += 1
                fragments.append(
                    BreathingFragment(
                        line_no=line_no,
                        fragment_no=fragment_no,
                        text=buffer,
                        display_text=f"{FULL_WIDTH_INDENT * indent_level}{buffer}",
                        indent_level=indent_level,
                        source_line_text=source_line_text,
                    )
                )
                buffer = ""
                indent_level = indent_level + 1 if pending_stop in SOFT_STOPS else 0
                pending_stop = None

            if buffer:
                fragment_no += 1
                fragments.append(
                    BreathingFragment(
                        line_no=line_no,
                        fragment_no=fragment_no,
                        text=buffer,
                        display_text=f"{FULL_WIDTH_INDENT * indent_level}{buffer}",
                        indent_level=indent_level,
                        source_line_text=source_line_text,
                    )
                )

        section_fragments.append(fragments)

    return section_fragments


def flatten_poem_lines(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 section 与句序展开原始 poem_line，供转轮和领读定位。"""
    return [line for section in sections for line in section.get("lines", [])]


def bounded_line_index(current: int, delta: int, line_count: int) -> int:
    """在词作句子范围内移动当前索引。"""
    if line_count <= 0:
        return 0
    return min(max(current + delta, 0), line_count - 1)


def fetch_reading_aids(
    poem_id: str,
    selected_text: str,
    line_no: int | None,
    include: list[str],
) -> dict[str, Any]:
    """手动请求当前词作的阅读辅助证据。"""
    if _public_demo_mode():
        return {
            "poem_id": poem_id,
            "selected_text": selected_text,
            "evidences": [],
            "allusions": [],
            "prosody": {},
            "errors": ["sample: Public Demo Mode 不调用实时阅读辅助工具"],
        }
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
            trust_env=False,
        )
    except httpx.RequestError as exc:
        raise ReaderAPIError("阅读辅助请求失败，正文仍可继续阅读") from exc
    data = _response_json(response)
    return data if isinstance(data, dict) else {}


def fetch_reading_workflow(
    poem_id: str,
    selected_text: str,
    line_no: int | None,
    max_candidates: int = 5,
) -> dict[str, Any]:
    """运行句级 Evidence Review Workflow，公共演示可降级到内置样例。"""
    if _public_demo_mode():
        return _demo_workflow_result(selected_text, line_no)
    payload = {
        "line_no": line_no,
        "selected_text": selected_text,
        "max_candidates": max_candidates,
    }
    try:
        response = httpx.post(
            _api_url(f"/api/poems/{poem_id}/reading-workflow"),
            json=payload,
            timeout=REVIEW_TIMEOUT_SECONDS,
            trust_env=False,
        )
        data = _response_json(response)
    except (httpx.RequestError, ReaderAPIError) as exc:
        if _public_demo_mode():
            return _demo_workflow_result(selected_text, line_no)
        raise ReaderAPIError("阅读工作流请求失败，正文仍可继续阅读") from exc
    return data if isinstance(data, dict) else {}


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
            <div class="reader-version">Reader v0.2.0-preview · 周邦彦词作</div>
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


def choose_poem(poem_id: str) -> None:
    """切换作品时清空上一首词的选句和证据。"""
    st.session_state.poem_id = poem_id
    st.session_state.selected_text = ""
    st.session_state.selected_line_no = None
    st.session_state.selected_line_text = None
    st.session_state.reading_aids = None
    st.session_state.last_included_tools = None
    st.session_state.allusion_candidates = None
    st.session_state.allusion_candidate_error = None
    st.session_state.pop("allusion_candidate_selection", None)
    st.session_state.current_line_index = 0
    st.session_state.is_playing = False
    st.session_state.last_advance_at = time.monotonic()


def choose_line(line_no: int, text: str) -> None:
    """把点击的词句同步到右侧查询框。"""
    st.session_state.selected_text = text
    st.session_state.selected_line_no = line_no
    st.session_state.selected_line_text = text
    st.session_state.reading_aids = None
    st.session_state.last_included_tools = None


def _allusion_candidate_items(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """兼容新 evidence preview 与旧候选响应的列表字段。"""
    if not data:
        return []
    items = data.get("items", data.get("candidates", []))
    return items if isinstance(items, list) else []


def _candidate_selection_payload(candidate: dict[str, Any]) -> tuple[int, str]:
    """候选回填只使用原文锚点，不使用任何查询变体。"""
    return int(candidate["line_no"]), str(candidate["anchor_text"])


def choose_allusion_candidate() -> None:
    """把 AI 候选的原文锚点与行号交给现有手动阅读辅助表单。"""
    selected = st.session_state.get("allusion_candidate_selection")
    candidates = _allusion_candidate_items(
        st.session_state.get("allusion_candidates")
    )
    if selected is None:
        return
    try:
        candidate = candidates[int(selected)]
    except (IndexError, TypeError, ValueError):
        return
    choose_line(*_candidate_selection_payload(candidate))


def change_reading_mode() -> None:
    """切换阅读模式时停止自动推进，并从当前索引继续。"""
    st.session_state.is_playing = False
    st.session_state.last_advance_at = time.monotonic()


def move_focus_line(delta: int, line_count: int) -> None:
    """手动移动转轮当前句，并重置领读计时。"""
    st.session_state.current_line_index = bounded_line_index(
        st.session_state.current_line_index,
        delta,
        line_count,
    )
    st.session_state.last_advance_at = time.monotonic()


def toggle_guided_playback(line_count: int) -> None:
    """切换领读播放状态；在末句重新播放时回到开头。"""
    if not st.session_state.is_playing and st.session_state.current_line_index >= line_count - 1:
        st.session_state.current_line_index = 0
    st.session_state.is_playing = not st.session_state.is_playing
    st.session_state.last_advance_at = time.monotonic()


def reset_guided_clock() -> None:
    st.session_state.last_advance_at = time.monotonic()


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


def _evidence_status_text(status: str, *, overall: bool = False) -> str:
    """把后端稳定状态转换成不暗示“已确认典故”的界面文案。"""
    labels = OVERALL_STATUS_LABELS if overall else EVIDENCE_STATUS_LABELS
    return labels.get(status, "状态未知")


def _candidate_type_label(candidate_type: str) -> str:
    """把稳定枚举转换为 Reader 使用的中文候选类型。"""
    return CANDIDATE_TYPE_LABELS.get(candidate_type, "待查")


def _truncate_evidence_text(
    text: str | None,
    limit: int = EVIDENCE_EXCERPT_LIMIT,
) -> tuple[str, str | None]:
    """返回默认摘要和可折叠全文；短文本不产生重复全文。"""
    normalized = (text or "").strip()
    if len(normalized) <= limit:
        return normalized, None
    return normalized[:limit].rstrip() + "…", normalized


def _evidence_count_text(result: dict[str, Any]) -> str:
    """生成不会把“展示 0”误称为截断的命中计数文案。"""
    hit_count = int(result.get("hit_count") or 0)
    displayed_count = int(result.get("displayed_count") or 0)
    if hit_count > 0 and displayed_count == 0:
        return f"命中 {hit_count} · 暂无可展示条目"
    text = f"命中 {hit_count} · 展示 {displayed_count}"
    if displayed_count > 0 and hit_count > displayed_count and result.get("truncated"):
        text += " · 已截断"
    return text


def _evidence_preview_html(result: dict[str, Any]) -> str:
    """渲染一个 query/source 的窄证据，所有外部文本先做 HTML 转义。"""
    source = html.escape(
        EVIDENCE_SOURCE_LABELS.get(result.get("source"), result.get("source") or "未知来源")
    )
    query = html.escape(str(result.get("query_used") or ""))
    status = html.escape(_evidence_status_text(str(result.get("status") or "")))
    count_text = html.escape(_evidence_count_text(result))
    parts = [
        "<div class='evidence-preview'>",
        f"<div class='evidence-preview-head'>{source} · {status}</div>",
        (
            "<div class='evidence-preview-meta'>"
            f"查询：{query} · {count_text}</div>"
        ),
    ]
    if result.get("error"):
        parts.append(
            "<div class='evidence-preview-error'>"
            f"{html.escape(str(result['error']))}</div>"
        )
    for item in result.get("items", []):
        title = html.escape(str(item.get("title") or "未命名候选"))
        excerpt, full_text = _truncate_evidence_text(item.get("evidence_text"))
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


def _long_evidence_entries(result: dict[str, Any]) -> list[tuple[str, str]]:
    """收集需要由折叠控件展示的长引文。"""
    entries: list[tuple[str, str]] = []
    for item in result.get("items", []):
        _, full_text = _truncate_evidence_text(item.get("evidence_text"))
        if full_text:
            entries.append((str(item.get("title") or "未命名候选"), full_text))
    return entries


def _all_candidates_have_no_evidence(candidates: list[dict[str, Any]]) -> bool:
    """判断是否所有候选都完整查过但没有任何外部命中。"""
    return bool(candidates) and all(
        candidate.get("overall_status") == "no_result" for candidate in candidates
    )


def _review_evidence_html(item: dict[str, Any]) -> str:
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


def _review_result_html(review: dict[str, Any]) -> str:
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


def _workflow_trace_step_html(step: dict[str, Any]) -> str:
    """把单步 trace 转为安全 HTML，供 UI 与单元测试共同使用。"""
    step_name = html.escape(str(step.get("step_name") or "unknown"))
    tool_name = html.escape(str(step.get("tool_name") or "-"))
    status = html.escape(
        WORKFLOW_STATUS_LABELS.get(str(step.get("status") or ""), "未知")
    )
    latency = int(step.get("latency_ms") or 0)
    input_summary = html.escape(str(step.get("input_summary") or "-"))
    output_summary = html.escape(str(step.get("output_summary") or "-"))
    error = html.escape(str(step.get("error") or ""))
    return (
        "<div class='evidence-preview-item'>"
        f"<strong>{step_name}</strong> · {status} · {latency} ms<br>"
        f"工具：{tool_name}<br>输入：{input_summary}<br>输出：{output_summary}"
        f"{'<br>错误：' + error if error else ''}</div>"
    )


def render_workflow_summary(result: dict[str, Any]) -> None:
    """展示工作流聚合结果和五步可观察 trace。"""
    st.markdown("#### AI 工作流")
    if result.get("sample_data"):
        st.info("Public Demo Mode：以下为 sample data，不是实时 LLM / CNKGraph 结果。")
    final_answer = str(result.get("final_answer") or "暂无可生成的审阅短注。")
    st.markdown(
        "<div class='evidence-card'><div class='evidence-anchor'>工作流结果</div>"
        f"<div class='evidence-body'>{html.escape(final_answer)}</div></div>",
        unsafe_allow_html=True,
    )
    st.caption(f"意图：{result.get('intent') or 'unknown'}")
    with st.expander("查看 Workflow Trace", expanded=False):
        for step in result.get("workflow_trace") or []:
            st.markdown(_workflow_trace_step_html(step), unsafe_allow_html=True)
    for error in result.get("errors") or []:
        st.caption(f"局部错误：{error}")


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
    """展示可观察工作流、手动工具表单和证据结果。"""
    st.markdown("### 阅读辅助")
    st.caption("AI 工作流只审阅现有 CNKGraph 候选证据，不代表最终定论。")
    if st.button(
        "运行证据审阅工作流",
        key=f"extract-allusions-{poem['poem_id']}",
        use_container_width=True,
    ):
        st.session_state.allusion_candidates = None
        st.session_state.allusion_candidate_error = None
        st.session_state.pop("allusion_candidate_selection", None)
        normalized_text = str(st.session_state.get("selected_text") or "").strip()
        if not normalized_text:
            st.session_state.allusion_candidate_error = "请先点击一句词或输入待查文本"
        else:
            line_no = (
                st.session_state.selected_line_no
                if normalized_text == st.session_state.selected_line_text
                else None
            )
            try:
                with st.spinner("正在路由、识别、查证并审阅候选证据"):
                    st.session_state.allusion_candidates = fetch_reading_workflow(
                        poem["poem_id"],
                        normalized_text,
                        line_no,
                    )
            except ReaderAPIError as exc:
                st.session_state.allusion_candidate_error = str(exc)

    if st.session_state.allusion_candidate_error:
        st.error(st.session_state.allusion_candidate_error)

    workflow_result = st.session_state.allusion_candidates
    if workflow_result:
        render_workflow_summary(workflow_result)
    candidates = _allusion_candidate_items(workflow_result)
    if st.session_state.allusion_candidates is not None and not candidates:
        st.markdown(
            "<div class='empty-state'>当前文本暂未识别到明确的典故/化用候选</div>",
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


def initialize_state(poems: list[dict[str, Any]]) -> None:
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
    if _public_demo_mode():
        st.info("Public Demo Mode 已启用：页面使用明确标记的 sample data。")

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
