"""Reader 调用本地 FastAPI 的薄客户端。

Streamlit 页面不直接连接数据库，也不直接调用 CNKGraph 或 LLM；它只通过这里的
HTTP 请求访问 FastAPI。这样前端、后端和外部工具的边界更容易看清。
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


def _api_url(path: str) -> str:
    """拼出本地 FastAPI 的完整 URL。"""
    base_url = os.getenv("QINGSHANG_API_BASE_URL", DEFAULT_API_BASE_URL)
    return f"{str(base_url).rstrip('/')}{path}"


def _response_json(response: httpx.Response) -> Any:
    """把 FastAPI 响应转换为 JSON，并统一包装前端可读错误。"""
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


def _local_http_client() -> httpx.Client:
    """创建访问本地 FastAPI 的客户端。

    `trust_env=False` 会忽略 Clash、系统代理或终端代理变量。Reader 访问的是
    127.0.0.1:8000，本机服务不应该绕到代理里。
    """
    return httpx.Client(timeout=API_TIMEOUT_SECONDS, trust_env=False)


@st.cache_data(ttl=30, show_spinner=False)
def fetch_poems() -> list[dict[str, Any]]:
    """读取周邦彦词作目录。"""
    try:
        with _local_http_client() as client:
            response = client.get(
                _api_url("/api/poems"),
                params={"author": "周邦彦", "limit": 500},
            )
    except httpx.RequestError as exc:
        raise ReaderAPIError("无法连接清商 FastAPI") from exc
    data = _response_json(response)
    return data if isinstance(data, list) else []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_poem(poem_id: str) -> dict[str, Any]:
    """读取一首词的完整结构。"""
    try:
        with _local_http_client() as client:
            response = client.get(_api_url(f"/api/poems/{poem_id}"))
    except httpx.RequestError as exc:
        raise ReaderAPIError("无法读取词作详情") from exc
    data = _response_json(response)
    return data if isinstance(data, dict) else {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_opening_lines(poem_ids: tuple[str, ...]) -> dict[str, str]:
    """并发读取当前目录页无标题词作的起句，不改变列表接口。"""

    def fetch_one(poem_id: str) -> tuple[str, str | None]:
        try:
            with _local_http_client() as client:
                response = client.get(_api_url(f"/api/poems/{poem_id}"))
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
        with httpx.Client(
            timeout=API_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            response = client.post(
                _api_url(f"/api/poems/{poem_id}/reading-aids"),
                json=payload,
            )
    except httpx.RequestError as exc:
        raise ReaderAPIError("阅读辅助请求失败，正文仍可继续阅读") from exc
    data = _response_json(response)
    return data if isinstance(data, dict) else {}


def fetch_allusion_candidates(poem_id: str) -> dict[str, Any]:
    """识别候选、查询 CNKGraph，并请求受控 Evidence Review。"""
    try:
        with httpx.Client(
            timeout=REVIEW_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            response = client.post(
                _api_url(f"/api/poems/{poem_id}/allusion-candidates/with-review"),
            )
    except httpx.RequestError as exc:
        raise ReaderAPIError("候选证据审阅请求失败，正文仍可继续阅读") from exc
    data = _response_json(response)
    return data if isinstance(data, dict) else {}
