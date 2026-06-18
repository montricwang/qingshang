from fastapi import APIRouter

from app.api.routes.poems import router as poems_router
from app.api.routes.poetry import router as poetry_router

api_router = APIRouter()
api_router.include_router(poems_router)
api_router.include_router(poetry_router)

__all__ = ["api_router"]
