"""自由文本赏析接口：接收一段词句并交给 LLM 解释。"""

from fastapi import APIRouter, HTTPException

from app.schemas.poetry import PoetryExplainRequest, PoetryExplainResponse
from app.services.llm_client import LLMClientError
from app.services.poetry import explain_poetry

router = APIRouter(prefix="/api/poetry", tags=["poetry"])


@router.post("/explain", response_model=PoetryExplainResponse)
async def explain(request: PoetryExplainRequest) -> PoetryExplainResponse:
    """赏析用户提交的文本。

    FastAPI 会先读取 POST 请求的 JSON 正文，再用 ``PoetryExplainRequest`` 校验；
    校验失败时框架直接返回 422，本函数不会被调用。
    """
    try:
        explanation = await explain_poetry(
            text=request.text,
            focus=request.focus,
        )
    except LLMClientError as exc:
        # 将内部服务异常转换成适合 API 调用者理解的 HTTP 502。
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # response_model 会再检查此对象，并把它编码成 JSON 响应。
    return PoetryExplainResponse(explanation=explanation)
