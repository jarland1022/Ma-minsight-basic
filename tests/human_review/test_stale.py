"""Tests for obsolete human-review cancellation helpers."""

from app.human_review.stale import is_system_error_human_query


def test_is_system_error_human_query_matches_llm_failure() -> None:
    assert is_system_error_human_query("自动调查未完成：LLM error: 404 Not Found，请协助确认。")


def test_is_system_error_human_query_ignores_business_question() -> None:
    assert not is_system_error_human_query("请确认源 IP 10.1.2.3 是否为公司例行扫描器？")
