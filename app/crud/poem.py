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
    stmt = (
        select(PoemModel)
        .where(PoemModel.poem_id == poem_id)
        .options(selectinload(PoemModel.sections).selectinload(PoemSectionModel.lines))
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def poem_to_list_item(poem: PoemModel):
    return {
        "poem_id": poem.poem_id,
        "author_order": poem.author_order,
        "author": poem.author,
        "dynasty": poem.dynasty,
        "tune_name": poem.tune_name,
        "musical_mode": poem.musical_mode,
        "title": poem.title,
        "series_label": poem.series_label,
    }


def poem_to_detail(poem: PoemModel):
    sections = sorted(poem.sections, key=lambda section: section.section_no)

    return {
        "poem_id": poem.poem_id,
        "author_order": poem.author_order,
        "author": poem.author,
        "dynasty": poem.dynasty,
        "tune_name": poem.tune_name,
        "musical_mode": poem.musical_mode,
        "title": poem.title,
        "series_label": poem.series_label,
        "preface": poem.preface,
        "full_text": poem.full_text,
        "sections": [
            {
                "section_no": section.section_no,
                "section_name": section.section_name,
                "lines": [
                    {
                        "global_line_no": line.global_line_no,
                        "section_line_no": line.section_line_no,
                        "text": line.text,
                    }
                    for line in sorted(
                        section.lines,
                        key=lambda line: line.section_line_no,
                    )
                ],
            }
            for section in sections
        ],
        "source": poem.source,
    }
