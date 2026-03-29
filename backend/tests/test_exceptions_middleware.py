"""Tests for exception handling middleware via HTTP client."""

import pytest


class TestExceptionMiddleware:
    async def test_app_error_returns_envelope(self, client):
        """AppError should be caught and returned as JSON envelope."""
        resp = await client.get("/api/jobs/nonexistent-uuid")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["data"] is None
        assert body["error"]["code"] == "JOB_NOT_FOUND"
        assert body["pagination"] is None

    async def test_unhandled_error_returns_500(self, client):
        """Unhandled exceptions should return a generic 500 error envelope."""
        resp = await client.get("/api/_test/error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "INTERNAL_ERROR"
