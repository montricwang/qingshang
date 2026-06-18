"""开发环境建表脚本，可通过 ``python -m app.db.init_db`` 单独运行。"""

import asyncio  # 在普通同步脚本入口中启动异步函数。
from importlib import import_module  # 按模块名动态导入 Python 模块。

from app.db.base import Base
from app.db.session import engine


def register_models() -> None:
    """导入模型模块，让 SQLAlchemy 执行类定义并登记所有表。"""
    _ = import_module("app.models.poem")


async def init_db() -> None:
    """连接数据库，并创建当前尚不存在的表。

    ``create_all`` 只补建缺失表，不负责修改已有表结构；正式结构变更通常应使用
    Alembic 迁移。本项目暂未引入 Alembic。
    """
    # 第一阶段：确保所有 ORM 模型都已经注册到 Base.metadata。
    register_models()

    print("Registered tables:", list(Base.metadata.tables.keys()))

    # 第二阶段：开启事务连接，把同步的 metadata.create_all 放进异步连接执行。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created successfully.")


if __name__ == "__main__":
    # 只有直接运行本模块时才建表；被其他模块 import 时不会执行。
    asyncio.run(init_db())
