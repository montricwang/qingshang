"""集中组装业务路由。

每个业务文件维护自己的 ``router``，本模块再把它们合并成一个 ``api_router``。
应用入口只需注册一次，新增路由时也不必继续修改 ``main.py``。
"""

from fastapi import APIRouter  # 一个可组合的“小型路由表”，本身不是 Web 应用。

from app.api.routes.poems import router as poems_router
from app.api.routes.poetry import router as poetry_router

# 以下代码在模块导入时运行，只负责组装路由表，不会执行具体接口函数。
api_router = APIRouter()
api_router.include_router(poems_router)
api_router.include_router(poetry_router)

__all__ = ["api_router"]
