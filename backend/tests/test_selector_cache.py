"""Tests for selector cache / learning mechanism."""

import pytest


class TestPagePattern:
    def test_create_pattern(self):
        from app.crawl.selector_cache import PagePattern

        p = PagePattern(
            job_links=["https://example.com/job/1"],
            job_card_selector="a.job-link",
            card_strategy="href",
            next_button_selector="a.next", page_number_selector="li.page-num",
            confidence=0.9,
        )
        assert p.card_strategy == "href"
        assert p.confidence == 0.9

    def test_pattern_with_click_strategy(self):
        from app.crawl.selector_cache import PagePattern

        p = PagePattern(
            job_links=[],
            job_card_selector="li.post_box",
            card_strategy="click",
            next_button_selector=None, page_number_selector=None,
            confidence=0.8,
        )
        assert p.card_strategy == "click"
        assert p.job_links == []


class TestSelectorCache:
    def test_not_locked_initially(self):
        from app.crawl.selector_cache import SelectorCache

        cache = SelectorCache()
        assert cache.is_locked() is False
        assert cache.get_locked() is None

    def test_single_record_does_not_lock(self):
        from app.crawl.selector_cache import SelectorCache, PagePattern

        cache = SelectorCache(lock_threshold=2)
        cache.record(PagePattern(
            job_links=[], job_card_selector="a.job",
            card_strategy="href", next_button_selector="a.next", page_number_selector="li.page-num", confidence=0.9,
        ))
        assert cache.is_locked() is False

    def test_two_consistent_records_lock(self):
        from app.crawl.selector_cache import SelectorCache, PagePattern

        cache = SelectorCache(lock_threshold=2)
        for _ in range(2):
            cache.record(PagePattern(
                job_links=[], job_card_selector="a.job",
                card_strategy="href", next_button_selector="a.next", page_number_selector="li.page-num", confidence=0.9,
            ))
        assert cache.is_locked() is True
        locked = cache.get_locked()
        assert locked.job_card_selector == "a.job"
        assert locked.card_strategy == "href"
        assert locked.next_button_selector == "a.next"
        assert locked.page_number_selector == "li.page-num"

    def test_inconsistent_records_reset_count(self):
        from app.crawl.selector_cache import SelectorCache, PagePattern

        cache = SelectorCache(lock_threshold=2)
        cache.record(PagePattern(
            job_links=[], job_card_selector="a.job",
            card_strategy="href", next_button_selector=None, page_number_selector=None, confidence=0.9,
        ))
        cache.record(PagePattern(
            job_links=[], job_card_selector="li.card",
            card_strategy="click", next_button_selector=None, page_number_selector=None, confidence=0.8,
        ))
        assert cache.is_locked() is False
        # Need 2 more consistent ones to lock
        cache.record(PagePattern(
            job_links=[], job_card_selector="li.card",
            card_strategy="click", next_button_selector=None, page_number_selector=None, confidence=0.8,
        ))
        assert cache.is_locked() is True

    def test_force_lock(self):
        from app.crawl.selector_cache import SelectorCache, LockedPattern

        cache = SelectorCache()
        cache.force_lock(LockedPattern(
            job_card_selector="li.post_box",
            card_strategy="click",
            next_button_selector=None, page_number_selector=None,
        ))
        assert cache.is_locked() is True
        assert cache.get_locked().job_card_selector == "li.post_box"

    def test_record_after_lock_does_not_change(self):
        from app.crawl.selector_cache import SelectorCache, PagePattern, LockedPattern

        cache = SelectorCache()
        cache.force_lock(LockedPattern(
            job_card_selector="a.original",
            card_strategy="href",
            next_button_selector=None, page_number_selector=None,
        ))
        cache.record(PagePattern(
            job_links=[], job_card_selector="a.different",
            card_strategy="href", next_button_selector=None, page_number_selector=None, confidence=1.0,
        ))
        assert cache.get_locked().job_card_selector == "a.original"

    def test_unlock_resets_state(self):
        from app.crawl.selector_cache import SelectorCache, LockedPattern

        cache = SelectorCache()
        cache.force_lock(LockedPattern(
            job_card_selector="a.job",
            card_strategy="href",
            next_button_selector=None, page_number_selector=None,
        ))
        assert cache.is_locked() is True
        cache.unlock()
        assert cache.is_locked() is False
        assert cache.get_locked() is None

    def test_custom_lock_threshold(self):
        from app.crawl.selector_cache import SelectorCache, PagePattern

        cache = SelectorCache(lock_threshold=3)
        pattern = PagePattern(
            job_links=[], job_card_selector="a.job",
            card_strategy="href", next_button_selector=None, page_number_selector=None, confidence=0.9,
        )
        cache.record(pattern)
        cache.record(pattern)
        assert cache.is_locked() is False  # need 3
        cache.record(pattern)
        assert cache.is_locked() is True
