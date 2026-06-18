"""自由文本赏析接口的请求和响应结构。"""

from pydantic import BaseModel, Field


class PoetryExplainRequest(BaseModel):
    """客户端提交的 JSON 正文；FastAPI 会自动创建并校验这个对象。"""

    text: str = Field(..., min_length=1, description="需要解释的词句或词作片段")
    focus: str | None = Field(
        default=None,
        description="可选的赏析重点，例如意象、情感、典故、格律、语言风格",
    )


class PoetryExplainResponse(BaseModel):
    """接口返回给客户端的 JSON 结构。"""

    explanation: str
