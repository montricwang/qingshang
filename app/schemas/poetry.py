from pydantic import BaseModel, Field


class PoetryExplainRequest(BaseModel):
    text: str = Field(..., min_length=1, description="需要解释的词句或词作片段")
    focus: str | None = Field(
        default=None,
        description="可选的赏析重点，例如意象、情感、典故、格律、语言风格",
    )


class PoetryExplainResponse(BaseModel):
    explanation: str
