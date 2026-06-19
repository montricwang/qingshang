"""在单个事务中用清洗结果替换周邦彦数据库记录。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 保证直接从其他工作目录运行脚本时仍能导入项目模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.models.poem import PoemLineModel, PoemModel, PoemSectionModel
from app.schemas.poem import PoemCore


INPUT_PATH = Path("data/generated/zhoubangyan_poems.json")
AUTHOR = "周邦彦"


def load_poems() -> list[PoemCore]:
    """读取 JSON，并用 PoemCore 验证每首词后返回对象列表。"""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件：{INPUT_PATH}")

    raw_data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    return [PoemCore.model_validate(item) for item in raw_data]


async def import_one_poem(session, poem: PoemCore) -> None:
    """把一首词及其片段、词句加入当前数据库会话。"""
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

    # flush 后才能取得数据库生成的主键，供子记录填写外键。
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
    """在一个事务中替换周邦彦全部数据。"""
    poems = load_poems()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(PoemModel).where(PoemModel.author == AUTHOR)
        )
        deleted_count = result.rowcount or 0

        await session.flush()

        for poem in poems:
            await import_one_poem(session, poem)

        # 删除和导入在同一 commit 生效，失败时不会只保存一部分新数据。
        await session.commit()

    print(f"删除旧数据：{deleted_count} 首")
    print(f"导入新数据：{len(poems)} 首")
    print("导入完成。")


if __name__ == "__main__":
    asyncio.run(main())
