"""定义诗词列表、详情和 LLM 分析接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.poem import get_poem_by_poem_id, list_poems
from app.schemas.allusion import (
    AllusionCandidateEvidenceResponse,
    AllusionCandidateReviewResponse,
    AllusionCandidateResponse,
)
from app.services.allusion_evidence import build_allusion_evidence_preview
from app.services.allusion_evidence_reviewer import build_allusion_evidence_review
from app.schemas.poem import PoemCore, PoemListItem
from app.services.allusion_candidate_extractor import extract_allusion_candidates
from app.services.poem_analyzer import analyze_poem

from app.db.session import get_db

router = APIRouter(
    prefix="/api/poems",
    tags=["poems"],
)


@router.get("", response_model=list[PoemListItem])
async def read_poem_list(
    author: str | None = Query(default=None, description="作者，例如：周邦彦"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PoemListItem]:
    """按作者筛选并分页返回诗词摘要。"""
    poem_models = await list_poems(
        db=db,
        author=author,
        limit=limit,
        offset=offset,
    )

    return [PoemListItem.model_validate(poem) for poem in poem_models]


@router.get("/{poem_id}", response_model=PoemCore)
async def read_poem_detail(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> PoemCore:
    """按稳定 poem_id 查询完整诗词，找不到时返回 HTTP 404。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)

    if poem is None:
        raise HTTPException(
            status_code=404,
            detail=f"找不到词作：{poem_id}",
        )

    return PoemCore.model_validate(poem)


@router.post("/{poem_id}/analyze")
async def analyze_poem_detail(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """读取指定诗词并返回 LLM 生成的结构化赏析。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)

    if poem is None:
        raise HTTPException(
            status_code=404,
            detail=f"找不到词作：{poem_id}",
        )

    try:
        analysis = await analyze_poem(poem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"分析失败：{exc}",
        ) from exc

    return analysis.model_dump(mode="json")


@router.post(
    "/{poem_id}/allusion-candidates",
    response_model=AllusionCandidateResponse,
)
async def read_allusion_candidates(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> AllusionCandidateResponse:
    """读取整首词，并让 LLM 识别值得后续查证的典故候选。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)
    if poem is None:
        raise HTTPException(status_code=404, detail=f"找不到词作：{poem_id}")

    try:
        return await extract_allusion_candidates(poem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"典故候选识别失败：{exc}",
        ) from exc


@router.post(
    "/{poem_id}/allusion-candidates/with-evidence",
    response_model=AllusionCandidateEvidenceResponse,
)
async def read_allusion_candidates_with_evidence(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> AllusionCandidateEvidenceResponse:
    """识别整首词的典故候选，并用现有 CNKGraph 工具自动查证。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)
    if poem is None:
        raise HTTPException(status_code=404, detail=f"找不到词作：{poem_id}")

    try:
        return await build_allusion_evidence_preview(poem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"典故候选自动查证失败：{exc}",
        ) from exc


@router.post(
    "/{poem_id}/allusion-candidates/with-review",
    response_model=AllusionCandidateReviewResponse,
)
async def read_allusion_candidates_with_review(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> AllusionCandidateReviewResponse:
    """生成候选证据预览，并让受控 Reviewer 逐候选审阅。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)
    if poem is None:
        raise HTTPException(status_code=404, detail=f"找不到词作：{poem_id}")

    try:
        return await build_allusion_evidence_review(poem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"候选证据审阅失败：{exc}",
        ) from exc
