"""串联候选、CNKGraph 与 Evidence Review 的固定可观察工作流。"""

from __future__ import annotations

from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.poem import get_poem_by_poem_id
from app.models.poem import PoemModel
from app.schemas.allusion import (
    AllusionCandidateItem,
    AllusionCandidateReviewedItem,
    EvidenceReviewResult,
)
from app.schemas.workflow import ReadingWorkflowResult, WorkflowTraceStep
from app.services.allusion_candidate_extractor import extract_allusion_candidates
from app.services.allusion_evidence import retrieve_evidence_for_candidates
from app.services.evidence_reviewer import review_evidence


def _latency_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def _summary(value: str, limit: int = 160) -> str:
    cleaned = " ".join(value.split())
    return cleaned if len(cleaned) <= limit else cleaned[:limit].rstrip() + "…"


def _intent_for_text(selected_text: str) -> str:
    """v0.2 preview 只开放典故/化用解释这一条可枚举意图。"""
    return "allusion_or_reference_explanation" if selected_text else "unknown"


def _resolve_selected_text(
    poem: PoemModel,
    line_no: int | None,
    selected_text: str | None,
) -> tuple[int | None, str]:
    lines = [line for section in poem.sections for line in section.lines]
    selected_line = next(
        (line for line in lines if line.global_line_no == line_no),
        None,
    )
    if line_no is not None and selected_line is None:
        raise ValueError(f"词作 {poem.poem_id} 中不存在第 {line_no} 句")

    text = (selected_text or "").strip()
    if not text and selected_line is not None:
        text = selected_line.text
    if not text:
        raise ValueError("line_no 和 selected_text 至少提供一个")
    if selected_line is not None and text not in selected_line.text:
        raise ValueError("selected_text 必须原样存在于指定 line_no 的原句中")

    resolved_line_no = line_no
    if resolved_line_no is None:
        matching_lines = [line for line in lines if text in line.text]
        if len(matching_lines) == 1:
            resolved_line_no = matching_lines[0].global_line_no
    return resolved_line_no, text


def _scope_candidates(
    candidates: list[AllusionCandidateItem],
    line_no: int | None,
    selected_text: str,
    max_candidates: int,
) -> list[AllusionCandidateItem]:
    scoped = []
    for candidate in candidates:
        if line_no is not None and candidate.line_no != line_no:
            continue
        if candidate.anchor_text not in selected_text and selected_text not in candidate.line_text:
            continue
        scoped.append(candidate)
        if len(scoped) >= max_candidates:
            break
    return scoped


def _final_answer(candidates: list[AllusionCandidateReviewedItem]) -> str:
    notes = [
        item.review_result.short_note
        for item in candidates
        if item.review_result.review_status == "reviewed"
        and item.review_result.short_note
    ]
    if not notes:
        return "现有候选证据不足，暂不生成确定解释。"
    return " ".join(notes) + " 以上为候选证据生成的审阅短注，仍需人工确认。"


def _pending_step(step_name: str, tool_name: str) -> WorkflowTraceStep:
    return WorkflowTraceStep(
        step_name=step_name,
        status="pending",
        tool_name=tool_name,
        output_summary="上游步骤失败，本步骤未执行。",
    )


async def run_reading_workflow(
    poem_id: str,
    *,
    db: AsyncSession,
    line_no: int | None = None,
    selected_text: str | None = None,
    max_candidates: int = 5,
) -> ReadingWorkflowResult:
    """运行固定五步工作流；候选级 Review 错误不会中断其他候选。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)
    if poem is None:
        raise LookupError(f"找不到词作：{poem_id}")
    resolved_line_no, text = _resolve_selected_text(poem, line_no, selected_text)

    trace: list[WorkflowTraceStep] = []
    errors: list[str] = []

    started = perf_counter()
    intent = _intent_for_text(text)
    trace.append(
        WorkflowTraceStep(
            step_name="intent_router",
            status="done",
            tool_name="rule_router",
            latency_ms=_latency_ms(started),
            input_summary=_summary(text),
            output_summary=intent,
        )
    )

    started = perf_counter()
    try:
        extracted = await extract_allusion_candidates(poem)
        candidates = _scope_candidates(
            extracted.candidates,
            resolved_line_no,
            text,
            max_candidates,
        )
        trace.append(
            WorkflowTraceStep(
                step_name="candidate_extraction",
                status="done",
                tool_name="llm_candidate_extractor",
                latency_ms=_latency_ms(started),
                input_summary=f"poem_id={poem_id}; text={_summary(text, 80)}",
                output_summary=f"保留 {len(candidates)} 个句级候选",
            )
        )
    except Exception:
        message = "候选识别失败"
        errors.append(message)
        trace.append(
            WorkflowTraceStep(
                step_name="candidate_extraction",
                status="error",
                tool_name="llm_candidate_extractor",
                latency_ms=_latency_ms(started),
                input_summary=f"poem_id={poem_id}",
                error=message,
            )
        )
        trace.extend(
            [
                _pending_step("evidence_retrieval", "cnkgraph_allusion+reference"),
                _pending_step("evidence_review", "llm_evidence_reviewer"),
                _pending_step("final_answer", "deterministic_aggregator"),
            ]
        )
        return ReadingWorkflowResult(
            poem_id=poem_id,
            line_no=resolved_line_no,
            selected_text=text,
            intent=intent,
            candidates=[],
            workflow_trace=trace,
            final_answer="候选识别失败，暂时无法生成审阅短注。",
            errors=errors,
        )

    started = perf_counter()
    evidence_response = await retrieve_evidence_for_candidates(poem, candidates)
    errors.extend(evidence_response.errors)
    evidence_count = sum(
        len(result.items)
        for candidate in evidence_response.items
        for result in candidate.evidence_results
    )
    trace.append(
        WorkflowTraceStep(
            step_name="evidence_retrieval",
            status="done",
            tool_name="cnkgraph_allusion+reference",
            latency_ms=_latency_ms(started),
            input_summary=f"{len(candidates)} 个候选",
            output_summary=f"获得 {evidence_count} 条可展示候选证据；局部错误 {len(evidence_response.errors)} 个",
        )
    )

    started = perf_counter()
    reviewed: list[AllusionCandidateReviewedItem] = []
    review_error_count = 0
    for candidate in evidence_response.items:
        try:
            review = await review_evidence(poem, candidate)
        except Exception:
            review_error_count += 1
            message = f"{candidate.anchor_text}: Evidence Review 失败"
            errors.append(message)
            review = EvidenceReviewResult(
                review_status="error",
                confidence="low",
                short_note=None,
                caveat=f"{message}；其他候选不受影响。",
            )
        reviewed.append(
            AllusionCandidateReviewedItem(
                **candidate.model_dump(),
                review_result=review,
            )
        )
    trace.append(
        WorkflowTraceStep(
            step_name="evidence_review",
            status="done",
            tool_name="llm_evidence_reviewer",
            latency_ms=_latency_ms(started),
            input_summary=f"{len(evidence_response.items)} 个候选证据包",
            output_summary=f"完成 {len(reviewed)} 个审阅；局部失败 {review_error_count} 个",
        )
    )

    started = perf_counter()
    answer = _final_answer(reviewed)
    trace.append(
        WorkflowTraceStep(
            step_name="final_answer",
            status="done",
            tool_name="deterministic_aggregator",
            latency_ms=_latency_ms(started),
            input_summary=f"{len(reviewed)} 个 Review 结果",
            output_summary=_summary(answer),
        )
    )
    return ReadingWorkflowResult(
        poem_id=poem_id,
        line_no=resolved_line_no,
        selected_text=text,
        intent=intent,
        candidates=reviewed,
        workflow_trace=trace,
        final_answer=answer,
        errors=errors,
    )
