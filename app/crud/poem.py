"""封装诗词读取查询。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.poem import PoemModel, PoemSectionModel


async def list_poems(
    db: AsyncSession,
    author: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[PoemModel]:
    """按作者筛选并分页返回 PoemModel 列表。"""
    stmt = select(PoemModel)

    if author is not None:
        stmt = stmt.where(PoemModel.author == author)

    stmt = (
        stmt.order_by(PoemModel.author, PoemModel.author_order)
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_poem_by_poem_id(
    db: AsyncSession,
    poem_id: str,
) -> PoemModel | None:
    """按 poem_id 返回词作，并预加载片段和词句；找不到时返回 None。"""
    stmt = (
        select(PoemModel)
        .where(PoemModel.poem_id == poem_id)
        .options(selectinload(PoemModel.sections).selectinload(PoemSectionModel.lines))
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()
