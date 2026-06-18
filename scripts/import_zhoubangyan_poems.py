"""把清洗后的周邦彦 JSON 导入数据库。

这是普通命令行脚本：直接运行时 main 会创建数据库会话，删除该作者旧数据，再在
同一事务中导入全部新数据。任一步失败，未提交的事务会回滚。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 保证直接从其他工作目录运行脚本时仍能导入项目模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete  # 构造数据库 DELETE 语句。

from app.db.session import AsyncSessionLocal  # 创建异步数据库会话的工厂。
from app.models.poem import PoemLineModel, PoemModel, PoemSectionModel
from app.schemas.poem import PoemCore  # 验证 JSON 并提供带类型的属性访问。


INPUT_PATH = Path("data/generated/zhoubangyan_poems.json")
AUTHOR = "周邦彦"


def load_poems() -> list[PoemCore]:
    """读取 JSON，并用 PoemCore 验证每首词后返回对象列表。"""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件：{INPUT_PATH}")

    raw_data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    return [PoemCore.model_validate(item) for item in raw_data]


async def import_one_poem(session, poem: PoemCore) -> None:
    """把一首 PoemCore 及其 sections/lines 加入当前数据库会话。

    ``session.add`` 只把对象加入待写队列；``flush`` 才发送当前 SQL，以便取得数据库
    自动生成的主键；最终是否永久保存由外层 ``commit`` 决定。
    """
    # 第一阶段：创建主表 ORM 对象并 flush，取得 poem_model.id。
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

    # 第二阶段：逐片写入 section，并取得其主键供 lines 外键使用。
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

        # 第三阶段：词句只需 add；外层最终 commit 前会统一 flush。
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

    # 与 FastAPI 的 Depends 不同，命令行脚本需要自己创建和管理 session。
    async with AsyncSessionLocal() as session:
        # 先删除旧数据；数据库的级联外键会同时删除关联 sections 和 lines。
        result = await session.execute(
            delete(PoemModel).where(PoemModel.author == AUTHOR)
        )
        deleted_count = result.rowcount or 0

        await session.flush()

        # 新数据逐首加入同一事务。
        for poem in poems:
            await import_one_poem(session, poem)

        # commit 是事务真正生效的边界；此前异常会使新旧数据都不被部分保存。
        await session.commit()

    print(f"删除旧数据：{deleted_count} 首")
    print(f"导入新数据：{len(poems)} 首")
    print("导入完成。")


if __name__ == "__main__":
    # asyncio.run 为本脚本创建事件循环，并运行异步 main 直到结束。
    asyncio.run(main())
