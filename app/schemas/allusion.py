"""定义整首词典故候选识别的窄输出结构。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CandidateType = Literal[
    "allusion",
    "literary_reference",
    "historical_place",
    "cultural_institution",
    "conventional_motif",
    "uncertain",
]
Confidence = Literal["high", "medium", "low"]


class AllusionCandidateItem(BaseModel):
    """一个只说明“为何值得查”的疑似典故候选。"""

    model_config = ConfigDict(extra="forbid")

    line_no: int = Field(..., ge=1)
    anchor_text: str = Field(..., min_length=1)
    candidate_type: CandidateType
    query: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    confidence: Confidence


class AllusionCandidateResponse(BaseModel):
    """一首词经过原文定位与数量限制后的候选列表。"""

    model_config = ConfigDict(extra="forbid")

    poem_id: str
    candidates: list[AllusionCandidateItem] = Field(default_factory=list, max_length=10)
