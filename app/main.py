"""创建 FastAPI 应用并注册项目路由。"""

from fastapi import FastAPI

from app.api.routes import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)

# 此处只注册路由；FastAPI 会在匹配的请求到来时调用对应函数。
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """返回服务健康状态。"""
    return {
        "status": "ok",
        "app_name": settings.app_name,
    }
