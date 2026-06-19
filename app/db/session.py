"""数据库引擎、会话工厂与 FastAPI 数据库依赖。"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 创建 engine 时不会立即连接；首次执行 SQL 时才会取得连接。
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """为一次请求提供并在请求结束后关闭数据库会话。

    FastAPI 会在遇到 Depends(get_db) 时自动调用本函数，把 yield 的 session
    注入路由参数，并在路由结束后继续完成清理。
    """
    async with AsyncSessionLocal() as session:
        yield session
