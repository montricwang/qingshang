"""封装 CNKGraph 近期只读接口。"""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import quote

import httpx

from app.core.config import settings

CNKGraphJSON = dict[str, Any] | list[Any] | str | int | float | bool | None


# ============================================================================
# 统一错误类型
# ============================================================================


class CNKGraphClientError(RuntimeError):
    """统一表示网络、HTTP 状态和 JSON 格式错误。"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ============================================================================
# 客户端类
# ============================================================================


class CNKGraphClient:
    """只负责发送请求并返回 CNKGraph 原始 JSON。"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.cnkgraph_base_url).rstrip("/")
        self.timeout = timeout or settings.cnkgraph_timeout_seconds
        self.transport = transport

    async def _request_json(
        self,
        method: str,
        path: str,
        json_body: Any = None,
    ) -> CNKGraphJSON:
        """发送一次请求，并把外部失败转换为稳定的客户端异常。"""
        request_kwargs = {"json": json_body} if json_body is not None else {}

        # 步骤 ① 发送 HTTP 请求
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.request(method, path, **request_kwargs)
        # 步骤 ② 网络层异常：超时和连接错误独立处理
        except httpx.TimeoutException as exc:
            raise CNKGraphClientError("CNKGraph 请求超时") from exc
        except httpx.RequestError as exc:
            raise CNKGraphClientError("CNKGraph 网络请求失败") from exc

        # 步骤 ③ HTTP 状态码校验：非 2xx 时抛出，保留 status_code 供上游判断 404 降级
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CNKGraphClientError(
                f"CNKGraph 返回 HTTP {response.status_code}",
                status_code=response.status_code,
            ) from exc

        # 步骤 ④ JSON 格式校验：响应体不是有效 JSON 时抛出
        try:
            return cast(CNKGraphJSON, response.json())
        except ValueError as exc:
            raise CNKGraphClientError("CNKGraph 返回的内容不是有效 JSON") from exc

    # -----------------------------------------------------------------------
    # CNKGraph 各接口方法：每个方法对应一个只读 API，只做路径拼接和类型收窄
    # -----------------------------------------------------------------------

    async def get_char(self, char: str) -> dict[str, Any]:
        path = f"/api/char/{quote(char, safe='')}"
        return cast(dict[str, Any], await self._request_json("GET", path))

    async def find_allusions(self, key: str) -> list[Any] | dict[str, Any]:
        return cast(
            list[Any] | dict[str, Any],
            await self._request_json(
                "POST",
                "/api/glossary/典故/find",
                {"key": key, "charIndex": "end"},
            ),
        )

    async def get_glossary(self, kind: str, item_id: int) -> dict[str, Any]:
        path = f"/api/glossary/{quote(kind, safe='')}/{item_id}"
        return cast(dict[str, Any], await self._request_json("GET", path))

    async def find_ci_tunes(self, key: str) -> list[Any] | dict[str, Any]:
        return cast(
            list[Any] | dict[str, Any],
            await self._request_json("POST", "/api/ciTune/find", {"key": key}),
        )

    async def get_ci_tune(self, tune_id: int) -> dict[str, Any]:
        return cast(dict[str, Any], await self._request_json("GET", f"/api/ciTune/{tune_id}"))

    async def match_ci_tune_pattern(self, content: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request_json("POST", "/api/ciTune/pattern", {"pattern": content}),
        )

    async def find_rhyme(self, char: str, book: str = "平水韵") -> dict[str, Any] | str:
        return cast(
            dict[str, Any] | str,
            await self._request_json(
                "POST",
                "/api/rhyme/find",
                {"Character": char, "Book": book},
            ),
        )

    async def analyze_reference(self, content: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await self._request_json("POST", "/api/tool/reference", {"content": content}),
        )

    async def get_writing(self, writing_id: int) -> dict[str, Any]:
        return cast(dict[str, Any], await self._request_json("GET", f"/api/writing/{writing_id}"))

    async def get_writing_tones(self, writing_id: int) -> dict[str, Any]:
        path = f"/api/writing/{writing_id}/tones"
        return cast(dict[str, Any], await self._request_json("GET", path))

    async def get_writing_book_links(self, writing_id: int) -> dict[str, Any]:
        path = f"/api/writing/{writing_id}/bookLinks"
        return cast(dict[str, Any], await self._request_json("GET", path))
