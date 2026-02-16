"""Tests for question_detector."""
import pytest

from src.question_detector import is_question


@pytest.mark.parametrize(
    "text",
    [
        "What is the API key?",
        "How do I deploy?",
        "When does the meeting start?",
        "Where is the config file?",
        "Why did it fail?",
        "Which table for bookings?",
        "Can we add a feature?",
        "Could you help?",
        "Does anyone know?",
        "Is there a way?",
    ],
)
def test_is_question_returns_true(text: str) -> None:
    assert is_question(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "Hello world",
        "The meeting is at 3pm",
        "I think we should deploy",
        "Config is in .env",
    ],
)
def test_is_question_returns_false(text: str) -> None:
    assert is_question(text) is False


def test_is_question_empty_and_none() -> None:
    assert is_question("") is False
    assert is_question(None) is False  # type: ignore
    assert is_question("   ") is False


def test_is_question_strips_whitespace() -> None:
    assert is_question("  How does it work?  ") is True
