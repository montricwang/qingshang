"""测试 Evidence Reviewer 的证据约束、短注边界与逐候选降级。"""

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.allusion import (
    AllusionCandidateEvidenceItem,
    AllusionCandidateEvidenceResponse,
    AllusionCandidateReviewResponse,
    AllusionCandidateReviewedItem,
    CandidateEvidenceResult,
    EvidenceReviewResult,
)
from app.schemas.cnkgraph import EvidenceItem
from app.services.allusion_evidence_reviewer import (
    build_allusion_evidence_review,
    build_evidence_review_prompt,
    normalize_evidence_review,
    review_allusion_candidate,
)


def make_poem() -> SimpleNamespace:
    return SimpleNamespace(
        poem_id="test-0001",
        author="周邦彦",
        dynasty="宋",
        tune_name="少年游",
        title=None,
    )


def make_candidate(
    anchor_text: str,
    items: list[EvidenceItem],
    *,
    line_text: str = "南都石黛扫晴山。",
) -> AllusionCandidateEvidenceItem:
    return AllusionCandidateEvidenceItem(
        line_no=1,
        line_text=line_text,
        anchor_text=anchor_text,
        candidate_type="literary_reference",
        query=anchor_text,
        query_variants=[anchor_text],
        reason="该原文短语可能涉及前代文献语词、成句或诗文化用，值得进一步查证。",
        confidence="high",
        evidence_results=[
            CandidateEvidenceResult(
                source="cnkgraph_reference",
                query_used=anchor_text,
                status="hit" if items else "no_result",
                hit_count=len(items),
                displayed_count=len(items),
                items=items,
            )
        ],
        overall_status="hit" if items else "no_result",
    )


def review_item(
    evidence_id: str,
    title: str,
    role: str,
    relevance: str,
    *,
    query: str = "南都石黛",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source": "cnkgraph_reference",
        "query_used": query,
        "title": title,
        "role": role,
        "relevance": relevance,
        "reason": "该条证据与原文短语可直接比对。",
    }


class EvidenceReviewerTests(IsolatedAsyncioTestCase):
    def test_prompt_forbids_search_memory_and_free_appreciation(self) -> None:
        candidate = make_candidate("燕台句", [])
        prompt = "\n".join(
            message["content"]
            for message in build_evidence_review_prompt(make_poem(), candidate, [])
        )

        self.assertIn("不得进行 Web 搜索", prompt)
        self.assertIn("不得凭记忆补充出处", prompt)
        self.assertIn("不是自由赏析者", prompt)
        self.assertIn("燕台句", prompt)
        self.assertIn("insufficient_evidence", prompt)

    def test_self_hit_is_downgraded_and_prior_source_is_best(self) -> None:
        evidence = [
            {
                "evidence_id": "e1",
                "source": "cnkgraph_reference",
                "query_used": "南都石黛",
                "title": "少年游",
                "source_ref": "宋 周邦彦 《少年游》",
                "context_relation": "current_poem",
            },
            {
                "evidence_id": "e2",
                "source": "cnkgraph_reference",
                "query_used": "南都石黛",
                "title": "玉台新咏序",
                "source_ref": "南朝 徐陵 《玉台新咏序》",
                "context_relation": "prior_source",
            },
            {
                "evidence_id": "e3",
                "source": "cnkgraph_reference",
                "query_used": "南都石黛",
                "title": "后代词作",
                "source_ref": "明 某作者 《后代词作》",
                "context_relation": "later_usage",
            },
        ]
        payload = {
            "review_status": "reviewed",
            "confidence": "high",
            "short_note": "“石黛”可据前代文献理解为画眉颜料，此处“晴山”可作谨慎的眉喻阅读。",
            "best_evidence": [
                review_item("e1", "少年游", "prior_source", "strong"),
                review_item("e2", "玉台新咏序", "prior_source", "strong"),
                review_item("e3", "后代词作", "prior_source", "strong"),
            ],
            "downgraded_evidence": [],
            "rejected_evidence": [],
            "caveat": None,
        }

        result = normalize_evidence_review(payload, evidence)

        self.assertEqual([item.evidence_id for item in result.best_evidence], ["e2"])
        roles = {item.evidence_id: item.role for item in result.downgraded_evidence}
        self.assertEqual(roles["e1"], "current_work_self_hit")
        self.assertEqual(roles["e3"], "later_reuse")
        self.assertTrue(result.short_note)

    async def test_nandu_shidai_with_xu_ling_evidence_generates_short_note(self) -> None:
        candidate = make_candidate(
            "南都石黛",
            [
                EvidenceItem(
                    tool_name="reference",
                    title="玉台新咏序",
                    evidence_text="南都石黛，最发双蛾。",
                    source_ref="南朝 徐陵 《玉台新咏序》",
                    context_relation="prior_source",
                )
            ],
        )
        response = {
            "review_status": "reviewed",
            "confidence": "high",
            "short_note": "“石黛”在候选文献中指画眉颜料，此处可谨慎联系“晴山”的眉喻。",
            "best_evidence": [
                review_item("e1", "玉台新咏序", "prior_source", "strong")
            ],
            "downgraded_evidence": [],
            "rejected_evidence": [],
            "caveat": None,
        }
        with patch(
            "app.services.allusion_evidence_reviewer.chat_completion",
            new=AsyncMock(return_value=json.dumps(response, ensure_ascii=False)),
        ):
            result = await review_allusion_candidate(make_poem(), candidate)

        self.assertEqual(result.review_status, "reviewed")
        self.assertEqual(result.confidence, "high")
        self.assertIsNotNone(result.short_note)

    async def test_yantai_without_evidence_is_insufficient_and_has_no_note(self) -> None:
        result = await review_allusion_candidate(
            make_poem(),
            make_candidate("燕台句", [], line_text="吟笺赋笔，犹记燕台句。"),
        )

        self.assertEqual(result.review_status, "insufficient_evidence")
        self.assertIsNone(result.short_note)

    async def test_one_review_error_does_not_abort_whole_poem(self) -> None:
        first = make_candidate("南都石黛", [])
        second = make_candidate("燕台句", [], line_text="犹记燕台句。")
        preview = AllusionCandidateEvidenceResponse(
            poem_id="test-0001",
            items=[first, second],
        )
        successful = EvidenceReviewResult(
            review_status="insufficient_evidence",
            confidence="low",
            short_note=None,
        )
        with (
            patch(
                "app.services.allusion_evidence_reviewer.build_allusion_evidence_preview",
                new=AsyncMock(return_value=preview),
            ),
            patch(
                "app.services.allusion_evidence_reviewer.review_allusion_candidate",
                new=AsyncMock(side_effect=[ValueError("bad json"), successful]),
            ),
        ):
            result = await build_allusion_evidence_review(make_poem())

        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].review_result.review_status, "error")
        self.assertEqual(
            result.items[1].review_result.review_status,
            "insufficient_evidence",
        )
        self.assertEqual(result.errors, ["南都石黛: Evidence Review 失败"])


def test_with_review_endpoint_returns_200_with_local_review_error() -> None:
    candidate = make_candidate("燕台句", [], line_text="犹记燕台句。")
    response_payload = AllusionCandidateReviewResponse(
        poem_id="test-0001",
        items=[
            AllusionCandidateReviewedItem(
                **candidate.model_dump(),
                review_result=EvidenceReviewResult(
                    review_status="error",
                    confidence="low",
                    short_note=None,
                    caveat="燕台句: Evidence Review 失败；其他候选不受影响。",
                ),
            )
        ],
        errors=["燕台句: Evidence Review 失败"],
    )

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with (
            patch(
                "app.api.routes.poems.get_poem_by_poem_id",
                new=AsyncMock(return_value=make_poem()),
            ),
            patch(
                "app.api.routes.poems.build_allusion_evidence_review",
                new=AsyncMock(return_value=response_payload),
            ),
        ):
            response = TestClient(app).post(
                "/api/poems/test-0001/allusion-candidates/with-review"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["review_result"]["review_status"] == "error"
