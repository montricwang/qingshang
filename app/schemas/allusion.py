"""定义整首词典故候选识别的窄输出结构。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.cnkgraph import EvidenceItem


CandidateType = Literal[
    "allusion",
    "literary_reference",
    "historical_place",
    "cultural_institution",
    "conventional_motif",
    "uncertain",
]
Confidence = Literal["high", "medium", "low"]
EvidenceStatus = Literal["hit", "no_result", "error"]
OverallEvidenceStatus = Literal["hit", "no_result", "partial_error", "error"]
EvidenceSource = Literal["cnkgraph_allusion", "cnkgraph_reference"]


class AllusionCandidateItem(BaseModel):
    """一个只说明“为何值得查”的疑似典故候选。"""

    model_config = ConfigDict(extra="forbid")

    line_no: int = Field(..., ge=1)
    line_text: str = ""
    anchor_text: str = Field(..., min_length=1)
    candidate_type: CandidateType
    query: str = Field(..., min_length=1)
    query_variants: list[str] = Field(default_factory=list)
    reason: str = Field(..., min_length=1)
    confidence: Confidence

    @model_validator(mode="after")
    def normalize_query_variants(self) -> "AllusionCandidateItem":
        """让查询变体有稳定兜底、顺序和数量上限。"""
        values = [self.anchor_text, *self.query_variants, self.query]
        normalized: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
            if len(normalized) >= 4:
                break
        self.query_variants = normalized
        return self


class AllusionCandidateResponse(BaseModel):
    """一首词经过原文定位与数量限制后的候选列表。"""

    model_config = ConfigDict(extra="forbid")

    poem_id: str
    candidates: list[AllusionCandidateItem] = Field(default_factory=list, max_length=10)


class CandidateEvidenceResult(BaseModel):
    """一次查询变体在一个 CNKGraph 工具中的窄结果。"""

    model_config = ConfigDict(extra="forbid")

    source: EvidenceSource
    query_used: str
    status: EvidenceStatus
    hit_count: int = Field(default=0, ge=0)
    displayed_count: int = Field(default=0, ge=0)
    truncated: bool = False
    items: list[EvidenceItem] = Field(default_factory=list)
    error: str | None = None


class AllusionCandidateEvidenceItem(AllusionCandidateItem):
    """一个候选及其逐查询、逐工具的外部证据预览。"""

    evidence_results: list[CandidateEvidenceResult] = Field(default_factory=list)
    overall_status: OverallEvidenceStatus


class AllusionCandidateEvidenceResponse(BaseModel):
    """整首词的典故候选与自动查证结果。"""

    model_config = ConfigDict(extra="forbid")

    poem_id: str
    items: list[AllusionCandidateEvidenceItem] = Field(default_factory=list, max_length=10)
    errors: list[str] = Field(default_factory=list)
