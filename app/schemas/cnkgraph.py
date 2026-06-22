"""定义清商 CNKGraph 工具层的窄输入输出结构。"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

RawCNKGraphData = dict[str, Any] | list[Any] | str | None
ReadingAidKind = Literal["allusion", "reference", "char", "ci_tune", "rhyme"]
EvidenceContextRelation = Literal["prior_source", "current_poem", "later_usage"]
RhymeChar = Annotated[str, Field(min_length=1, max_length=1)]


class EvidenceItem(BaseModel):
    """一条带来源的外部证据候选。"""

    source: str = "cnkgraph"
    tool_name: str
    anchor_text: str | None = None
    title: str | None = None
    claim: str | None = None
    evidence_text: str | None = None
    source_ref: str | None = None
    match_status: Literal["exact", "candidate", "no_result", "error"] = "candidate"
    context_relation: EvidenceContextRelation | None = None
    raw: RawCNKGraphData = None


class AllusionCandidate(BaseModel):
    """典故检索返回的候选，不表示已经完成语境确认。"""

    keyword: str
    title: str | None = None
    explanation: str | None = None
    source_text: str | None = None
    source_ref: str | None = None
    raw: dict[str, Any] | None = None


class ProsodyAid(BaseModel):
    """词牌、平仄和押韵相关的阅读辅助。"""

    tune_name: str | None = None
    tone_pattern: str | None = None
    rhyme_info: list[EvidenceItem] = Field(default_factory=list)
    raw: RawCNKGraphData = None


class ReadingAidRequest(BaseModel):
    """阅读器请求的文本位置与工具范围。"""

    selected_text: str | None = Field(default=None, min_length=1)
    line_no: int | None = Field(default=None, ge=1)
    include: list[ReadingAidKind] = Field(
        default_factory=lambda: [
            "allusion",
            "reference",
            "char",
            "ci_tune",
            "rhyme",
        ]
    )


class ReadingAidResponse(BaseModel):
    """单首词阅读所需的候选证据集合。"""

    poem_id: str
    selected_text: str | None = None
    line_no: int | None = None
    evidences: list[EvidenceItem] = Field(default_factory=list)
    allusions: list[AllusionCandidate] = Field(default_factory=list)
    prosody: ProsodyAid | None = None
    errors: list[str] = Field(default_factory=list)


class ReferenceRequest(BaseModel):
    """出处与化用分析请求。"""

    content: str = Field(..., min_length=1)


class RhymeRequest(BaseModel):
    """一个或多个字的韵书查询请求。"""

    chars: list[RhymeChar] = Field(..., min_length=1, max_length=30)
    book: str = Field(default="平水韵", min_length=1)
