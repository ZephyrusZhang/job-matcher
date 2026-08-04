"""Version 1 of the agent framework API."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["Agent Auth"])

__all__ = ["api_router"]
