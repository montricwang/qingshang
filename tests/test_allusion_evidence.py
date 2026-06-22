"""测试典故候选自动查证的命中、空结果和局部降级。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.allusion import AllusionCandidateItem, AllusionCandidateResponse
from app.schemas.cnkgraph import AllusionCandidate, EvidenceItem
from app.services.cnkgraph_client import CNKGraphClientError


def make_extracted_candidates() -> AllusionCandidateResponse:
    return AllusionCandidateResponse(
        poem_id="test-0001",
        candidates=[
            AllusionCandidateItem(
                line_no=1,
                line_text="吟笺赋笔，犹记燕台句。",
                anchor_text="燕台句",
                candidate_type="literary_reference",
                query="燕台句",
                query_variants=["燕台句", "报错词"],
                reason="该原文短语可能涉及前代文献或文学语句的化用，值得进一步查证。",
                confidence="high",
            ),
            AllusionCandidateItem(
                line_no=2,
                line_text="梨花榆火催寒食。",
                anchor_text="寒食",
                candidate_type="cultural_institution",
                query="寒食",
                query_variants=["寒食"],
                reason="该原文短语可能涉及节令、礼俗、制度或文化名物，值得进一步查证。",
                confidence="high",
            ),
        ],
    )


async def fake_allusion_lookup(query: str) -> list[AllusionCandidate]:
    if query == "燕台句":
        return [
            AllusionCandidate(
                keyword=query,
                title="燕台诗候选",
                explanation="外部工具返回的候选释义",
                source_text="外部工具返回的引文",
                source_ref="CNKGraph 典故",
            )
        ]
    if query == "报错词":
        raise CNKGraphClientError("CNKGraph 请求超时", status_code=503)
    return []


async def fake_reference_lookup(query: str) -> list[EvidenceItem]:
    if query == "报错词":
        raise CNKGraphClientError("CNKGraph 返回 HTTP 404", status_code=404)
    return []


def test_with_evidence_endpoint_keeps_local_errors_local() -> None:
    poem = SimpleNamespace(poem_id="test-0001")

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with (
            patch(
                "app.api.routes.poems.get_poem_by_poem_id",
                new=AsyncMock(return_value=poem),
            ),
            patch(
                "app.services.allusion_evidence.extract_allusion_candidates",
                new=AsyncMock(return_value=make_extracted_candidates()),
            ),
            patch(
                "app.services.allusion_evidence.build_allusion_candidates",
                new=AsyncMock(side_effect=fake_allusion_lookup),
            ),
            patch(
                "app.services.allusion_evidence.build_reference_evidences",
                new=AsyncMock(side_effect=fake_reference_lookup),
            ),
        ):
            response = TestClient(app).post(
                "/api/poems/test-0001/allusion-candidates/with-evidence"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert all(item["evidence_results"] for item in data["items"])
    assert data["items"][0]["overall_status"] == "partial_error"
    assert data["items"][1]["overall_status"] == "no_result"
    statuses = {
        result["status"]
        for item in data["items"]
        for result in item["evidence_results"]
    }
    assert {"hit", "no_result", "error"}.issubset(statuses)
    assert data["errors"] == [
        "燕台句 / cnkgraph_allusion / 报错词: CNKGraph 请求超时"
    ]
    hit_item = data["items"][0]["evidence_results"][0]["items"][0]
    assert hit_item["title"] == "燕台诗候选"
    assert hit_item["raw"] is None
