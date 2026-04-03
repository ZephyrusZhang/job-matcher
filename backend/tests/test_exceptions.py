from app.exceptions import (
    AppError, ResumeNotFoundError, NoFavoritesError,
    CrawlInProgressError, FileFormatError, FileTooLargeError,
    JobNotFoundError, ReportNotFoundError,
)


def test_app_error():
    err = AppError("TEST", "test message", 400)
    assert err.code == "TEST"
    assert err.message == "test message"
    assert err.status_code == 400


def test_specific_errors():
    errors = [
        (ResumeNotFoundError(), "RESUME_NOT_FOUND", 422),
        (NoFavoritesError(), "NO_FAVORITES", 422),
        (CrawlInProgressError(), "CRAWL_IN_PROGRESS", 409),
        (FileFormatError(), "UNSUPPORTED_FORMAT", 415),
        (FileTooLargeError(), "FILE_TOO_LARGE", 413),
        (JobNotFoundError(), "JOB_NOT_FOUND", 404),
        (ReportNotFoundError(), "REPORT_NOT_FOUND", 404),
    ]
    for err, code, status in errors:
        assert err.code == code
        assert err.status_code == status
