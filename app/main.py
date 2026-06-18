"""Web 应用入口。

运行 ``uvicorn app.main:app`` 时，Uvicorn 会先导入这个模块，再找到下面名为
``app`` 的 FastAPI 对象。之后不是我们主动逐个调用路由函数，而是 FastAPI 根据
收到的 HTTP 请求，自动选择并调用已经注册的函数。
"""

from fastapi import FastAPI  # 创建 ASGI Web 应用；Uvicorn 会调用它处理 HTTP 请求。

from app.api.routes import api_router
from app.core.config import settings

# 创建应用对象时，FastAPI 会准备路由表、OpenAPI 文档和请求处理机制。
app = FastAPI(title=settings.app_name)

# 把 api_router 中收集的所有业务路由复制到应用路由表中。此处只是“注册”，
# 真正的路由函数会在对应 HTTP 请求到来时由 FastAPI 自动调用。
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """返回服务健康状态。

    ``@app.get`` 是装饰器：模块导入时，它会把本函数登记为 GET /health 的处理器；
    请求到来前函数不会执行。返回的字典会由 FastAPI 自动序列化为 JSON。
    """
    return {
        "status": "ok",
        "app_name": settings.app_name,
    }
