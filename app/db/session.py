"""数据库引擎、会话工厂与 FastAPI 数据库依赖。"""

from collections.abc import AsyncGenerator  # 标注“可异步 yield 值”的函数。

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Engine 保存数据库连接配置并管理连接池；这里不会立刻连接数据库。
# 第一次真正执行 SQL 时，SQLAlchemy 才会从连接池取得或创建连接。
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

# sessionmaker 是“会话工厂”。调用 AsyncSessionLocal() 才会创建一个会话对象。
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """为一次 HTTP 请求提供数据库会话。

    FastAPI 看到 ``Depends(get_db)`` 后会自动推进这个异步生成器：
    1. 进入 ``async with`` 并创建 session；
    2. 把 ``yield`` 的 session 传给路由函数的 ``db`` 参数；
    3. 路由结束后继续执行生成器，离开 ``async with`` 并关闭 session。

    因此业务代码不需要手动调用或关闭它，这正是依赖注入体现控制反转的地方。
    """
    async with AsyncSessionLocal() as session:
        yield session
