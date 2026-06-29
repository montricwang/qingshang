"""Reader 调用本地 FastAPI 的薄客户端。

Streamlit 页面不直接连接数据库，也不直接调用 CNKGraph 或 LLM；
它只通过这里的 HTTP 请求访问 FastAPI。

数据流：
Streamlit 组件 → fetch_*() → httpx → FastAPI → 返回 dict
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import streamlit as st

from apps.reader.config import (
    API_TIMEOUT_SECONDS,
    DEFAULT_API_BASE_URL,
    REVIEW_TIMEOUT_SECONDS,
)


class ReaderAPIError(RuntimeError):
    """表示 Reader 无法从本地 FastAPI 获得有效数据。"""


# ---------------------------------------------------------------------------
# 底层 HTTP 请求工具
# ---------------------------------------------------------------------------

def _api_url(path: str) -> str:
    """拼出本地 FastAPI 的完整 URL（默认 http://127.0.0.1:8000）。"""
    base_url = os.getenv("QINGSHANG_API_BASE_URL", DEFAULT_API_BASE_URL)
    return f"{str(base_url).rstrip('/')}{path}"


def _response_json(response: httpx.Response) -> Any:
    """把 FastAPI 响应统一转为 dict/list，并包装可读错误。

    不在此处做类型检查；上层 fetch 函数可信任后端 response_model 的约定。
    """
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


def _client(timeout: float = API_TIMEOUT_SECONDS) -> httpx.Client:
    """创建访问本地 FastAPI 的同步客户端。

    trust_env=False：忽略系统代理变量。Reader 访问的是 127.0.0.1:8000，
    本机服务不应绕到代理。
    """
    return httpx.Client(timeout=timeout, trust_env=False)


def _get_json(path: str, params: dict | None = None, timeout: float = API_TIMEOUT_SECONDS) -> Any:
    """统一的 GET 请求 → JSON 响应。所有 fetch_poem/fetch_poems 共用。"""
    try:
        with _client(timeout) as client:
            response = client.get(_api_url(path), params=params)
    except httpx.RequestError as exc:
        raise ReaderAPIError("无法连接清商 FastAPI") from exc
    return _response_json(response)


def _post_json(path: str, body: dict, timeout: float = API_TIMEOUT_SECONDS) -> Any:
    """统一的 POST 请求 → JSON 响应。reading-aids/候选审阅共用。"""
    try:
        with _client(timeout) as client:
            response = client.post(_api_url(path), json=body)
    except httpx.RequestError as exc:
        raise ReaderAPIError("请求失败，正文仍可继续阅读") from exc
    return _response_json(response)


# ---------------------------------------------------------------------------
# 上层 fetch 函数：每个函数对应一个后端接口
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def fetch_poems() -> list[dict[str, Any]]:
    """读取周邦彦词作目录（缓存 30 秒）。"""
    data = _get_json("/api/poems", params={"author": "周邦彦", "limit": 500})
    return data if isinstance(data, list) else []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_poem(poem_id: str) -> dict[str, Any]:
    """读取一首词的完整结构（缓存 30 秒）。"""
    data = _get_json(f"/api/poems/{poem_id}")
    return data if isinstance(data, dict) else {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_opening_lines(poem_ids: tuple[str, ...]) -> dict[str, str]:
    """并发读取当前目录页无标题词作的起句，不改变列表接口（缓存 5 分钟）。"""

    def _first_line(poem_id: str) -> tuple[str, str | None]:
        # 步骤 ① 请求词作详情
        try:
            data = _get_json(f"/api/poems/{poem_id}")
        except (httpx.RequestError, ReaderAPIError):
            return poem_id, None
        # 步骤 ② 从详情中提取第一句的 text
        sections = data.get("sections", []) if isinstance(data, dict) else []
        lines = sections[0].get("lines", []) if sections else []
        opening = lines[0].get("text") if lines else None
        return poem_id, opening

    # 步骤 ③ 并发执行多个详情请求
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(_first_line, poem_ids)
    # 步骤 ④ 只保留有起句的结果
    return {poem_id: opening for poem_id, opening in results if opening}


def fetch_reading_aids(
    poem_id: str,
    selected_text: str,
    line_no: int | None,
    include: list[str],
) -> dict[str, Any]:
    """手动请求当前词作的阅读辅助证据（不缓存，每次重新查询）。"""
    data = _post_json(
        f"/api/poems/{poem_id}/reading-aids",
        body={"selected_text": selected_text, "line_no": line_no, "include": include},
    )
    return data if isinstance(data, dict) else {}


def fetch_allusion_candidates(poem_id: str) -> dict[str, Any]:
    """识别候选、查询 CNKGraph、请求受控 Evidence Review（3 分钟超时）。"""
    data = _post_json(
        f"/api/poems/{poem_id}/allusion-candidates/with-review",
        body={},
        timeout=REVIEW_TIMEOUT_SECONDS,
    )
    return data if isinstance(data, dict) else {}
