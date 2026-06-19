"""LLM 诗词分析结果必须满足的结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineExplanation(BaseModel):
    """某一句原文的翻译与赏析。"""

    global_line_no: int = Field(..., ge=1)
    section_name: str | None = None
    section_line_no: int = Field(..., ge=1)
    original: str
    translation: str
    explanation: str


class ImageryItem(BaseModel):
    """一个意象及其在词中的作用。"""

    image: str
    meaning: str


class PoemAnalysis(BaseModel):
    """经过 Pydantic 校验的整首词结构化分析。"""

    poem_id: str
    tune_name: str
    title: str | None = None

    summary: str = Field(..., description="整首词大意")
    emotional_flow: str = Field(..., description="情感流动")
    style: str = Field(..., description="风格分析")

    imagery: list[ImageryItem] = Field(default_factory=list)
    line_explanations: list[LineExplanation]
