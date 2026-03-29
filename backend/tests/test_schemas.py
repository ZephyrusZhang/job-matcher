"""Tests for response schemas."""

import pytest
from pydantic import ValidationError


class TestApiResponse:
    def test_success_response(self):
        from app.schemas.common import ApiResponse

        resp = ApiResponse.ok(data={"key": "value"})
        assert resp.success is True
        assert resp.data == {"key": "value"}
        assert resp.error is None
        assert resp.pagination is None

    def test_success_response_with_pagination(self):
        from app.schemas.common import ApiResponse, PaginationMeta

        pagination = PaginationMeta(page=1, page_size=20, total=100, total_pages=5)
        resp = ApiResponse.ok(data=[1, 2, 3], pagination=pagination)
        assert resp.success is True
        assert resp.pagination.total == 100
        assert resp.pagination.total_pages == 5

    def test_error_response(self):
        from app.schemas.common import ApiResponse

        resp = ApiResponse.fail(code="NOT_FOUND", message="岗位不存在")
        assert resp.success is False
        assert resp.data is None
        assert resp.error.code == "NOT_FOUND"
        assert resp.error.message == "岗位不存在"

    def test_pagination_meta(self):
        from app.schemas.common import PaginationMeta

        p = PaginationMeta(page=2, page_size=10, total=25, total_pages=3)
        assert p.page == 2
        assert p.page_size == 10

    def test_pagination_from_total(self):
        from app.schemas.common import PaginationMeta

        p = PaginationMeta.from_total(page=1, page_size=20, total=55)
        assert p.total_pages == 3  # ceil(55/20) = 3

    def test_pagination_from_total_exact(self):
        from app.schemas.common import PaginationMeta

        p = PaginationMeta.from_total(page=1, page_size=20, total=40)
        assert p.total_pages == 2

    def test_pagination_from_total_zero(self):
        from app.schemas.common import PaginationMeta

        p = PaginationMeta.from_total(page=1, page_size=20, total=0)
        assert p.total_pages == 0


class TestExceptions:
    def test_app_error(self):
        from app.exceptions import AppError

        err = AppError(code="TEST", message="test error", status_code=400)
        assert err.code == "TEST"
        assert err.message == "test error"
        assert err.status_code == 400

    def test_resume_not_found(self):
        from app.exceptions import ResumeNotFoundError

        err = ResumeNotFoundError()
        assert err.status_code == 422
        assert err.code == "RESUME_NOT_FOUND"

    def test_no_favorites(self):
        from app.exceptions import NoFavoritesError

        err = NoFavoritesError()
        assert err.status_code == 422

    def test_crawl_in_progress(self):
        from app.exceptions import CrawlInProgressError

        err = CrawlInProgressError()
        assert err.status_code == 409

    def test_file_format_error(self):
        from app.exceptions import FileFormatError

        err = FileFormatError()
        assert err.status_code == 415

    def test_file_too_large(self):
        from app.exceptions import FileTooLargeError

        err = FileTooLargeError()
        assert err.status_code == 413

    def test_job_not_found(self):
        from app.exceptions import JobNotFoundError

        err = JobNotFoundError()
        assert err.status_code == 404

    def test_report_not_found(self):
        from app.exceptions import ReportNotFoundError

        err = ReportNotFoundError()
        assert err.status_code == 404
