"""Custom exceptions and global exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base business exception."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ResumeNotFoundError(AppError):
    def __init__(self):
        super().__init__("RESUME_NOT_FOUND", "请先上传简历", 422)


class NoFavoritesError(AppError):
    def __init__(self):
        super().__init__("NO_FAVORITES", "该公司暂无收藏岗位", 422)


class CrawlInProgressError(AppError):
    def __init__(self):
        super().__init__("CRAWL_IN_PROGRESS", "该公司已有正在进行的爬取任务", 409)


class FileFormatError(AppError):
    def __init__(self):
        super().__init__("UNSUPPORTED_FORMAT", "仅支持 PDF 和 DOCX 格式", 415)


class FileTooLargeError(AppError):
    def __init__(self):
        super().__init__("FILE_TOO_LARGE", "文件大小不能超过 10MB", 413)


class JobNotFoundError(AppError):
    def __init__(self):
        super().__init__("JOB_NOT_FOUND", "岗位不存在", 404)


class ReportNotFoundError(AppError):
    def __init__(self):
        super().__init__("REPORT_NOT_FOUND", "报告不存在", 404)


_ERROR_ENVELOPE = {
    "success": False,
    "data": None,
    "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"},
    "pagination": None,
}


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {"code": exc.code, "message": exc.message},
                "pagination": None,
            },
        )

    @app.middleware("http")
    async def catch_unhandled_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unexpected error")
            return JSONResponse(status_code=500, content=_ERROR_ENVELOPE)
