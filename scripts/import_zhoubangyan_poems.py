from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.models.poem import PoemLineModel, PoemModel, PoemSectionModel
from app.schemas.poem import PoemCore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


INPUT_PATH = Path("data/generated/zhoubangyan_poems.json")
AUTHOR = "周邦彦"


def load_poems() -> list[PoemCore]:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件：{INPUT_PATH}")

    raw_data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    return [PoemCore.model_validate(item) for item in raw_data]


async def import_one_poem(session, poem: PoemCore) -> None:
    poem_model = PoemModel(
        poem_id=poem.poem_id,
        author_order=poem.author_order,
        author=poem.author,
        dynasty=poem.dynasty,
        tune_name=poem.tune_name,
        musical_mode=poem.musical_mode,
        title=poem.title,
        series_label=poem.series_label,
        preface=poem.preface,
        full_text=poem.full_text,
        source=poem.source,
    )

    session.add(poem_model)
    await session.flush()

    if poem_model.id is None:
        raise RuntimeError(f"插入 poem 后没有得到 id：{poem.poem_id}")

    poem_db_id = poem_model.id

    for section in poem.sections:
        section_model = PoemSectionModel(
            poem_db_id=poem_db_id,
            section_no=section.section_no,
            section_name=section.section_name,
        )

        session.add(section_model)
        await session.flush()

        if section_model.id is None:
            raise RuntimeError(
                f"插入 section 后没有得到 id：{poem.poem_id} / section {section.section_no}"
            )

        section_db_id = section_model.id

        for line in section.lines:
            line_model = PoemLineModel(
                poem_db_id=poem_db_id,
                section_db_id=section_db_id,
                global_line_no=line.global_line_no,
                section_line_no=line.section_line_no,
                text=line.text,
            )

            session.add(line_model)


async def main() -> None:
    poems = load_poems()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(PoemModel).where(PoemModel.author == AUTHOR)
        )
        deleted_count = result.rowcount or 0

        await session.flush()

        for poem in poems:
            await import_one_poem(session, poem)

        await session.commit()

    print(f"删除旧数据：{deleted_count} 首")
    print(f"导入新数据：{len(poems)} 首")
    print("导入完成。")


if __name__ == "__main__":
    asyncio.run(main())
