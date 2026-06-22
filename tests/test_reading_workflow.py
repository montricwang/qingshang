"""测试固定阅读工作流的 trace、局部降级与 API 契约。"""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.allusion import (
    AllusionCandidateEvidenceItem,
    AllusionCandidateEvidenceResponse,
    AllusionCandidateItem,
    AllusionCandidateResponse,
    CandidateEvidenceResult,
    EvidenceReviewResult,
)
from app.schemas.workflow import ReadingWorkflowResult, WorkflowTraceStep
from app.services.reading_workflow import run_reading_workflow


def make_poem() -> SimpleNamespace:
    line = SimpleNamespace(
        global_line_no=1,
        section_line_no=1,
        text="南都石黛扫晴山，衣薄耐朝寒。",
    )
    return SimpleNamespace(
        poem_id="test-0001",
        author="周邦彦",
        dynasty="宋",
        tune_name="少年游",
        title=None,
        preface=None,
        sections=[SimpleNamespace(section_no=1, section_name="全篇", lines=[line])],
    )


def make_candidate(anchor_text: str) -> AllusionCandidateItem:
    return AllusionCandidateItem(
        line_no=1,
        line_text="南都石黛扫晴山，衣薄耐朝寒。",
        anchor_text=anchor_text,
        candidate_type="literary_reference",
        query=anchor_text,
        query_variants=[anchor_text],
        reason="该原文短语可能涉及前代文献语词、成句或诗文化用，值得进一步查证。",
        confidence="high",
    )


def with_evidence(candidate: AllusionCandidateItem) -> AllusionCandidateEvidenceItem:
    return AllusionCandidateEvidenceItem(
        **candidate.model_dump(),
        evidence_results=[
            CandidateEvidenceResult(
                source="cnkgraph_reference",
                query_used=candidate.anchor_text,
                status="no_result",
            )
        ],
        overall_status="no_result",
    )


class ReadingWorkflowTests(IsolatedAsyncioTestCase):
    def test_trace_schema_keeps_stable_step_fields(self) -> None:
        step = WorkflowTraceStep(
            step_name="intent_router",
            status="done",
            tool_name="rule_router",
            latency_ms=3,
            input_summary="南都石黛",
            output_summary="allusion_or_reference_explanation",
        )

        self.assertEqual(step.status, "done")
        self.assertEqual(step.latency_ms, 3)

    async def test_workflow_records_five_steps_and_survives_one_review_error(self) -> None:
        first = make_candidate("南都石黛")
        second = make_candidate("衣薄耐朝寒")
        extraction = AllusionCandidateResponse(
            poem_id="test-0001",
            candidates=[first, second],
        )
        evidence = AllusionCandidateEvidenceResponse(
            poem_id="test-0001",
            items=[with_evidence(first), with_evidence(second)],
        )
        insufficient = EvidenceReviewResult(
            review_status="insufficient_evidence",
            confidence="low",
            short_note=None,
            caveat="现有候选证据不足。",
        )

        with (
            patch(
                "app.services.reading_workflow.get_poem_by_poem_id",
                new=AsyncMock(return_value=make_poem()),
            ),
            patch(
                "app.services.reading_workflow.extract_allusion_candidates",
                new=AsyncMock(return_value=extraction),
            ),
            patch(
                "app.services.reading_workflow.retrieve_evidence_for_candidates",
                new=AsyncMock(return_value=evidence),
            ),
            patch(
                "app.services.reading_workflow.review_evidence",
                new=AsyncMock(side_effect=[ValueError("bad review"), insufficient]),
            ),
        ):
            result = await run_reading_workflow(
                "test-0001",
                db=object(),
                line_no=1,
                selected_text="南都石黛扫晴山，衣薄耐朝寒。",
                max_candidates=2,
            )

        self.assertEqual(
            [step.step_name for step in result.workflow_trace],
            [
                "intent_router",
                "candidate_extraction",
                "evidence_retrieval",
                "evidence_review",
                "final_answer",
            ],
        )
        self.assertTrue(all(step.status == "done" for step in result.workflow_trace))
        self.assertEqual(result.candidates[0].review_result.review_status, "error")
        self.assertEqual(
            result.candidates[1].review_result.review_status,
            "insufficient_evidence",
        )
        self.assertIn("证据不足", result.final_answer)
        self.assertNotIn("确定解释：", result.final_answer)
        self.assertEqual(len(result.errors), 1)


def test_reading_workflow_endpoint_keeps_local_errors_in_200_response() -> None:
    payload = ReadingWorkflowResult(
        poem_id="test-0001",
        line_no=1,
        selected_text="南都石黛",
        intent="allusion_or_reference_explanation",
        candidates=[],
        workflow_trace=[
            WorkflowTraceStep(
                step_name="evidence_review",
                status="done",
                tool_name="llm_evidence_reviewer",
                output_summary="局部失败 1 个",
            )
        ],
        final_answer="现有候选证据不足，暂不生成确定解释。",
        errors=["南都石黛: Evidence Review 失败"],
    )

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "app.api.routes.poems.run_reading_workflow",
            new=AsyncMock(return_value=payload),
        ):
            response = TestClient(app).post(
                "/api/poems/test-0001/reading-workflow",
                json={"line_no": 1, "selected_text": "南都石黛"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["errors"] == ["南都石黛: Evidence Review 失败"]
    assert response.json()["workflow_trace"][0]["step_name"] == "evidence_review"
