from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.poem import get_poem_by_poem_id, list_poems
from app.schemas.poem import PoemCore, PoemListItem
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
