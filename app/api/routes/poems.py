"""诗词查询与分析接口。

本文件最重要的框架行为：
1. ``@router.get/post`` 在导入时注册函数，而不是立即调用函数。
2. ``Query`` 告诉 FastAPI 如何从 URL 查询参数取值和校验。
3. ``Depends(get_db)`` 告诉 FastAPI 在调用函数前先创建数据库会话。
4. ``response_model`` 让 FastAPI 在响应前再次校验并序列化返回值。
"""

from __future__ import annotations

# FastAPI 路由、依赖注入、HTTP 异常和查询参数声明工具。
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession  # 异步数据库会话的类型。

# 项目内部导入：查询数据库、定义响应形状、调用分析服务、提供数据库会话。
from app.crud.poem import get_poem_by_poem_id, list_poems
from app.schemas.poem import PoemCore, PoemListItem
from app.services.poem_analyzer import analyze_poem

from app.db.session import get_db

router = APIRouter(
    prefix="/api/poems",
    tags=["poems"],
)


@router.get("", response_model=list[PoemListItem])
async def read_poem_list(
    author: str | None = Query(default=None, description="作者，例如：周邦彦"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PoemListItem]:
    """查询诗词列表。

    输入：FastAPI 从 URL 读取 ``author``、``limit``、``offset``；``db`` 不由调用者
    提供，而是框架执行 ``get_db`` 后自动注入。输出：诗词列表，返回前会按
    ``list[PoemListItem]`` 校验并转换为 JSON。
    """
    # 数据访问交给 CRUD 层，本函数只负责接收 HTTP 参数和组织 HTTP 响应。
    poem_models = await list_poems(
        db=db,
        author=author,
        limit=limit,
        offset=offset,
    )

    # from_attributes=True 允许 Pydantic 从 SQLAlchemy 对象属性读取字段。
    return [PoemListItem.model_validate(poem) for poem in poem_models]


@router.get("/{poem_id}", response_model=PoemCore)
async def read_poem_detail(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> PoemCore:
    """按稳定 poem_id 查询完整诗词，找不到时返回 HTTP 404。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)

    if poem is None:
        # 抛出 HTTPException 会中断函数；FastAPI 会把它转换成 HTTP 错误响应。
        raise HTTPException(
            status_code=404,
            detail=f"找不到词作：{poem_id}",
        )

    # sections/lines 已由 CRUD 查询预加载，Pydantic 可以同步读取嵌套对象。
    return PoemCore.model_validate(poem)


@router.post("/{poem_id}/analyze")
async def analyze_poem_detail(
    poem_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """读取指定诗词并请求 LLM 生成结构化赏析。

    输入：路径中的 ``poem_id`` 和自动注入的数据库会话。
    输出：可直接序列化成 JSON 的赏析字典。
    """
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)

    if poem is None:
        raise HTTPException(
            status_code=404,
            detail=f"找不到词作：{poem_id}",
        )

    try:
        # await 会暂停当前请求，等待网络调用完成；事件循环仍可处理其他请求。
        analysis = await analyze_poem(poem)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"分析失败：{exc}",
        ) from exc

    return analysis.model_dump(mode="json")
