from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    pagination: PaginationMeta | None = None

    @classmethod
    def ok(cls, data: Any = None, pagination: PaginationMeta | None = None):
        return cls(success=True, data=data, pagination=pagination)

    @classmethod
    def error_response(cls, code: str, message: str, details: dict | None = None):
        return cls(
            success=False,
            error=ErrorDetail(code=code, message=message, details=details or {}),
        )
