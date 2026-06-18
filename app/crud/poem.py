"""诗词数据访问层（CRUD 中当前只实现 Read）。

路由函数不需要知道 SQL 细节，只调用这里的函数。SQLAlchemy 会把 ``select`` 表达式
编译成 PostgreSQL SQL，并把查询结果行还原成 ORM 对象。
"""

from __future__ import annotations

# select 构建 SELECT 查询；AsyncSession 执行查询；selectinload 预加载 ORM 关系。
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
    """按作者筛选并分页查询诗词摘要。

    输入：数据库会话、可选作者、分页数量和偏移量。
    输出：PoemModel 对象列表；此查询不加载 sections，因为列表接口不需要正文。
    """
    # 先构造查询表达式。此时只是 Python 对象，还没有访问数据库。
    stmt = select(PoemModel)

    if author is not None:
        # where 返回加入条件后的新查询；SQL 参数会由 SQLAlchemy 安全绑定。
        stmt = stmt.where(PoemModel.author == author)

    # 排序和分页同样只是继续构造 SQL 表达式。
    stmt = (
        stmt.order_by(PoemModel.author, PoemModel.author_order)
        .offset(offset)
        .limit(limit)
    )

    # execute 才是真正把查询发给数据库；await 等待异步驱动返回结果。
    result = await db.execute(stmt)
    # scalars() 只取每行中的 PoemModel，all() 取出全部结果。
    return list(result.scalars().all())


async def get_poem_by_poem_id(
    db: AsyncSession,
    poem_id: str,
) -> PoemModel | None:
    """按 poem_id 查询一首词及其片段和词句。

    ``selectinload`` 会安排额外查询批量加载关系，避免返回 ORM 对象后再读取
    ``sections`` 时临时访问数据库，也避免异步环境中的延迟加载错误。
    """
    stmt = (
        select(PoemModel)
        .where(PoemModel.poem_id == poem_id)
        .options(selectinload(PoemModel.sections).selectinload(PoemSectionModel.lines))
    )

    result = await db.execute(stmt)
    # 有一条就返回 ORM 对象，没有就返回 None；多于一条则报错，暴露数据异常。
    return result.scalar_one_or_none()
