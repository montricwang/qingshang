from fastapi import APIRouter, HTTPException

from app.schemas.poetry import PoetryExplainRequest, PoetryExplainResponse
from app.services.llm_client import LLMClientError
from app.services.poetry import explain_poetry

router = APIRouter(prefix="/api/poetry", tags=["poetry"])


@router.post("/explain", response_model=PoetryExplainResponse)
async def explain(request: PoetryExplainRequest) -> PoetryExplainResponse:
    try:
        explanation = await explain_poetry(
            text=request.text,
            focus=request.focus,
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return PoetryExplainResponse(explanation=explanation)
