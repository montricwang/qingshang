"""使用 mock 验证 CNKGraph 客户端、适配器和降级行为。"""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

import httpx

from app.api.routes.cnkgraph import build_poem_reading_aids
from app.main import app
from app.schemas.cnkgraph import ReadingAidRequest
from app.services.cnkgraph_client import CNKGraphClient, CNKGraphClientError
from app.services.cnkgraph_tools import build_allusion_candidates


class EmptyAllusionClient:
    async def find_allusions(self, key: str) -> list[object]:
        return []


class CNKGraphAsyncTests(IsolatedAsyncioTestCase):
    async def test_allusion_adapter_returns_empty_list_for_empty_result(self) -> None:
        result = await build_allusion_candidates(
            "前度刘郎",
            client=EmptyAllusionClient(),  # type: ignore[arg-type]
        )

        self.assertEqual(result, [])

    async def test_client_raises_stable_error_for_non_2xx(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "unavailable"}, request=request)

        client = CNKGraphClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(CNKGraphClientError) as caught:
            await client.get_char("中")

        self.assertEqual(caught.exception.status_code, 503)

    async def test_client_get_does_not_send_json_body(self) -> None:
        captured_content = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_content
            captured_content = request.content
            return httpx.Response(200, json={"ModernDictionary": []}, request=request)

        client = CNKGraphClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        )

        await client.get_char("中")

        self.assertEqual(captured_content, b"")

    async def test_reading_aids_degrades_when_tool_fails(self) -> None:
        poem = SimpleNamespace(
            poem_id="test-0001",
            tune_name="瑞龙吟",
            sections=[
                SimpleNamespace(
                    lines=[SimpleNamespace(global_line_no=1, text="前度刘郎今又来")]
                )
            ],
        )
        request = ReadingAidRequest(
            line_no=1,
            include=["allusion"],
        )

        with (
            patch(
                "app.api.routes.cnkgraph.get_poem_by_poem_id",
                new=AsyncMock(return_value=poem),
            ),
            patch(
                "app.api.routes.cnkgraph.build_allusion_candidates",
                new=AsyncMock(side_effect=CNKGraphClientError("CNKGraph 请求超时")),
            ),
        ):
            response = await build_poem_reading_aids(
                poem_id="test-0001",
                request=request,
                db=object(),  # type: ignore[arg-type]
            )

        self.assertEqual(response.selected_text, "前度刘郎今又来")
        self.assertEqual(response.allusions, [])
        self.assertEqual(response.errors, ["allusion: CNKGraph 请求超时"])


class CNKGraphRouteTests(TestCase):
    def test_openapi_exposes_tool_layer_without_labelize(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("/api/cnkgraph/allusions", paths)
        self.assertIn("/api/cnkgraph/reference", paths)
        self.assertIn("/api/poems/{poem_id}/reading-aids", paths)
        self.assertIn(
            "/api/poems/{poem_id}/allusion-candidates/with-evidence",
            paths,
        )
        self.assertIn(
            "/api/poems/{poem_id}/allusion-candidates/with-review",
            paths,
        )
        self.assertFalse(any("labelize" in path for path in paths))
