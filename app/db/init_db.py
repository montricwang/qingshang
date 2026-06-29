"""开发环境建表脚本，可通过 ``python -m app.db.init_db`` 单独运行。"""

import asyncio
from importlib import import_module

from app.db.base import Base
from app.db.session import engine


def register_models() -> None:
    """导入模型模块，将表声明登记到 Base.metadata。"""
    _ = import_module("app.models.poem")


async def init_db() -> None:
    """创建尚不存在的数据库表。"""
    # 步骤 ① 导入 ORM 模型，让 SQLAlchemy 将表声明登记到 Base.metadata
    register_models()

    print("Registered tables:", list(Base.metadata.tables.keys()))

    # 步骤 ② 调用 create_all 建表；只补建缺失表，不会迁移已有表结构。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
