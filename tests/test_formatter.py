"""Tests for formatter."""
from datetime import datetime

import pytest

from src.formatter import build_post_content, format_reply


def test_format_reply() -> None:
    text = format_reply(
        answerer_name="Alice",
        answer_time=datetime(2024, 2, 13),
        answer_summary="Use the API key in .env",
        thread_link="https://example.com/thread",
    )
    assert "Alice" in text
    assert "Feb 13" in text
    assert "Use the API key in .env" in text
    assert "https://example.com/thread" in text
    assert "View original thread" in text


def test_format_reply_empty_link() -> None:
    text = format_reply(
        answerer_name="Bob",
        answer_time="Jan 1",
        answer_summary="Summary",
        thread_link="",
    )
    assert "Bob" in text
    assert "View original thread" in text
    assert "https://" not in text or "View original thread: " not in text or "View original thread" in text


def test_build_post_content_with_mention() -> None:
    post = build_post_content(
        answer_time=datetime(2024, 2, 13),
        answer_summary="It works",
        thread_link="https://lark.com/thread",
        answerer_open_id="ou_123",
    )
    assert "zh_cn" in post
    assert "en_us" in post
    content = post["zh_cn"]["content"]
    at_elem = next((e for line in content for e in line if e.get("tag") == "at"), None)
    assert at_elem is not None
    assert at_elem["user_id"] == "ou_123"
    link_elem = next((e for line in content for e in line if e.get("tag") == "a"), None)
    assert link_elem is not None
    assert link_elem["href"] == "https://lark.com/thread"


def test_build_post_content_without_mention() -> None:
    post = build_post_content(
        answer_time="Feb 13",
        answer_summary="It works",
        thread_link="",
        answerer_open_id=None,
    )
    content = post["zh_cn"]["content"]
    text_elems = [e for line in content for e in line if e.get("tag") == "text"]
    assert any("someone" in str(e.get("text", "")) for e in text_elems)
    assert not any(e.get("tag") == "at" for line in content for e in line)
