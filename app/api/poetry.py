from fastapi import APIRouter, HTTPException

from app.schemas.poetry import PoetryExplainRequest, PoetryExplainResponse
from app.services.poetry import explain_poetry

router = APIRouter(prefix="/api/poetry", tags=["poetry"])


@router.post("/explain", response_model=PoetryExplainResponse)
async def explain(request: PoetryExplainRequest):
    try:
        explanation = await explain_poetry(
            text=request.text,
            focus=request.focus,
        )
        return PoetryExplainResponse(explanation=explanation)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"{type(exc).__name__}: {str(exc)}"
        ) from exc
