from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.poetry import router as poetry_router
from app.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(chat_router)
app.include_router(poetry_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
    }
