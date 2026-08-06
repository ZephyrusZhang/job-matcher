"""When a crawl counts as failed.

The case being pinned down: an agent burned through all 64 turns without ever
writing ``output.json``, and the crawl was recorded as ``completed`` with 0
jobs — no error message, nothing to retry on, and the company's listing simply
went empty.
"""

from app.agents.crawler import MAX_TURNS, CrawlOutcome


def test_jobs_found_is_a_success():
    outcome = CrawlOutcome(jobs=[{"title": "后端"}], code="print()", turns=8, wrote_output=True)
    assert outcome.failure_reason() is None


def test_running_out_of_turns_without_output_is_a_failure():
    outcome = CrawlOutcome(jobs=[], code=None, turns=MAX_TURNS, wrote_output=False)

    reason = outcome.failure_reason()
    assert reason is not None
    assert str(MAX_TURNS) in reason
    assert "output.json" in reason


def test_an_empty_output_file_is_still_a_success():
    """A careers page with nothing open is a real answer, not a failure."""
    outcome = CrawlOutcome(jobs=[], code="print()", turns=5, wrote_output=True)
    assert outcome.failure_reason() is None


def test_an_agent_crash_without_output_is_a_failure():
    outcome = CrawlOutcome(jobs=[], code=None, turns=3, wrote_output=False, error="boom")
    assert "boom" in (outcome.failure_reason() or "")


def test_cancelling_is_not_a_failure():
    """Stopping is the user's decision; it must not surface as an error."""
    outcome = CrawlOutcome(jobs=[], code=None, turns=2, wrote_output=False, cancelled=True)
    assert outcome.failure_reason() is None


def test_stopping_short_without_output_still_fails():
    """Finishing early is no better than running out of turns if nothing came of it."""
    outcome = CrawlOutcome(jobs=[], code=None, turns=4, wrote_output=False)

    reason = outcome.failure_reason()
    assert reason is not None
    assert "output.json" in reason
