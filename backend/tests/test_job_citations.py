"""Tests for :job[...] citation extraction."""

from app.utils.job_citations import extract_job_ids

A = "3f2a9c10-7b4d-4e88-9a15-c0d3e5f61a27"
B = "8c1e04b2-33af-4d9e-b6c7-1e2f4a5b9d80"


def test_extracts_block_and_inline_markers():
    text = f"推荐这个：\n\n:job[{A}]\n\n也可以看看 :job[{B}]，方向接近。"
    assert extract_job_ids(text) == [A, B]


def test_dedupes_preserving_first_appearance():
    assert extract_job_ids(f":job[{B}] … :job[{A}] … :job[{B}]") == [B, A]


def test_normalizes_case():
    assert extract_job_ids(f":job[{A.upper()}]") == [A]


def test_allows_whitespace_inside_brackets():
    assert extract_job_ids(f":job[  {A}  ]") == [A]


def test_ignores_fenced_code():
    text = f"用法：\n\n```\n:job[{A}]\n```\n\n真实引用 :job[{B}]"
    assert extract_job_ids(text) == [B]


def test_ignores_tilde_fenced_code():
    assert extract_job_ids(f"~~~\n:job[{A}]\n~~~\n") == []


def test_ignores_inline_code():
    assert extract_job_ids(f"格式是 `:job[{A}]` 这样") == []


def test_rejects_malformed_uuid():
    short = A[:-1]
    assert extract_job_ids(f":job[{short}]") == []
    assert extract_job_ids(":job[not-a-uuid]") == []
    assert extract_job_ids(f":job[{A}") == []


def test_handles_empty_and_none():
    assert extract_job_ids("") == []
    assert extract_job_ids(None) == []
    assert extract_job_ids("完全没有引用的一段正文") == []
