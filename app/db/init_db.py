import asyncio
from importlib import import_module

from app.db.base import Base
from app.db.session import engine


def register_models() -> None:
    _ = import_module("app.models.poem")


async def init_db() -> None:
    register_models()

    print("Registered tables:", list(Base.metadata.tables.keys()))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
