"""定义可观察 Evidence Review Workflow 的输入、trace 与输出契约。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.allusion import (
    AllusionCandidateReviewedItem,
    EvidenceReviewResult,
)


WorkflowStepStatus = Literal["pending", "running", "done", "error"]


class WorkflowTraceStep(BaseModel):
    """固定工作流中一个可观察步骤的最终执行记录。"""

    model_config = ConfigDict(extra="forbid")

    step_name: str = Field(..., min_length=1)
    status: WorkflowStepStatus
    tool_name: str | None = None
    latency_ms: int = Field(default=0, ge=0)
    input_summary: str = ""
    output_summary: str = ""
    error: str | None = None


class ReadingWorkflowRequest(BaseModel):
    """用户从 Reader 发起一次句级或短语级工作流的参数。"""

    model_config = ConfigDict(extra="forbid")

    line_no: int | None = Field(default=None, ge=1)
    selected_text: str | None = Field(default=None, min_length=1)
    max_candidates: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def require_text_or_line(self) -> "ReadingWorkflowRequest":
        if self.line_no is None and not (self.selected_text or "").strip():
            raise ValueError("line_no 和 selected_text 至少提供一个")
        if self.selected_text is not None:
            self.selected_text = self.selected_text.strip()
        return self


class ReadingWorkflowResult(BaseModel):
    """候选、证据审阅、trace 与谨慎最终回答的聚合结果。"""

    model_config = ConfigDict(extra="forbid")

    poem_id: str
    line_no: int | None = None
    selected_text: str
    intent: str
    candidates: list[AllusionCandidateReviewedItem] = Field(default_factory=list)
    workflow_trace: list[WorkflowTraceStep] = Field(default_factory=list)
    final_answer: str
    errors: list[str] = Field(default_factory=list)


__all__ = [
    "EvidenceReviewResult",
    "ReadingWorkflowRequest",
    "ReadingWorkflowResult",
    "WorkflowTraceStep",
]
