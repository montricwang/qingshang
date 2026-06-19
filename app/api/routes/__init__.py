"""将业务路由聚合为应用使用的总路由。"""

from fastapi import APIRouter

from app.api.routes.poems import router as poems_router

# 导入时只登记规则，不会执行具体路由函数。
api_router = APIRouter()
api_router.include_router(poems_router)

__all__ = ["api_router"]
