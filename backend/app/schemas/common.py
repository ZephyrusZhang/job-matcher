"""Unified API response envelope and pagination."""

import math
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def from_total(cls, page: int, page_size: int, total: int) -> "PaginationMeta":
        total_pages = math.ceil(total / page_size) if page_size > 0 and total > 0 else 0
        return cls(page=page, page_size=page_size, total=total, total_pages=total_pages)


class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    error: ErrorDetail | None = None
    pagination: PaginationMeta | None = None

    @classmethod
    def ok(cls, data: Any = None, pagination: PaginationMeta | None = None) -> "ApiResponse":
        return cls(success=True, data=data, pagination=pagination)

    @classmethod
    def fail(cls, code: str, message: str, details: dict | None = None) -> "ApiResponse":
        return cls(
            success=False,
            data=None,
            error=ErrorDetail(code=code, message=message, details=details),
        )
