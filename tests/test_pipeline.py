"""Tests for pipeline."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline import DONT_KNOW_REPLY, handle_message, index_reply


@pytest.fixture
def mock_dependencies(monkeypatch):
    """Mock store, lark_client, formatter, question_detector, embeddings for pipeline tests."""
    mock_store = MagicMock()
    mock_store.find_similar_questions.return_value = []
    mock_store.find_similar_question.return_value = None

    def fake_embed(text):
        return [0.1] * 384

    monkeypatch.setattr("src.pipeline.store", mock_store)
    monkeypatch.setattr("src.pipeline.embeddings.embed", fake_embed)
    monkeypatch.setattr("src.pipeline.question_detector", MagicMock())
    monkeypatch.setattr("src.pipeline.lark_client", MagicMock())
    monkeypatch.setattr("src.pipeline.formatter", MagicMock())
    monkeypatch.setattr("src.pipeline.ANSWERED_ONCE_CHAT_IDS", [])  # allow any chat
    return mock_store


def test_handle_message_skips_empty_text(mock_dependencies) -> None:
    handle_message(
        chat_id="oc_1",
        message_id="om_1",
        message_text="",
        sender_id="ou_1",
    )
    mock_store = mock_dependencies
    mock_store.find_similar_question.assert_not_called()


def test_handle_message_skips_non_question(mock_dependencies) -> None:
    from src.pipeline import question_detector

    question_detector.is_question.return_value = False
    handle_message(
        chat_id="oc_1",
        message_id="om_1",
        message_text="Hello world",
        sender_id="ou_1",
    )
    mock_store = mock_dependencies
    mock_store.find_similar_question.assert_not_called()


def test_handle_message_no_match_sends_dont_know(mock_dependencies) -> None:
    from src.pipeline import question_detector

    question_detector.is_question.return_value = True
    lark = __import__("src.pipeline", fromlist=["lark_client"]).lark_client
    lark.send_text_message.return_value = "om_reply"

    handle_message(
        chat_id="oc_1",
        message_id="om_1",
        message_text="How do I deploy?",
        sender_id="ou_1",
    )

    lark.send_text_message.assert_called_once()
    args, kwargs = lark.send_text_message.call_args
    assert args[0] == "oc_1"
    assert args[1] == DONT_KNOW_REPLY
    assert kwargs.get("root_id") == "om_1"
    assert kwargs.get("post_content") is None


def test_handle_message_with_match_sends_post(mock_dependencies, monkeypatch) -> None:
    from src.pipeline import formatter, lark_client, question_detector

    monkeypatch.setattr("src.pipeline.ANSWER_MODE", "top_1")
    question_detector.is_question.return_value = True
    mock_store = mock_dependencies
    mock_record = MagicMock(
        question_text="Q?",
        answer_text="A",
        answerer_name="Alice",
        answer_time=datetime(2024, 2, 13),
        chat_id="oc_1",
        root_message_id="om_root",
        thread_id="om_root",
        answerer_open_id="ou_alice",
    )
    mock_store.find_similar_question.return_value = mock_record
    formatter.build_post_content.return_value = {"post": "content"}
    formatter.format_reply.return_value = "Plain text fallback"
    lark_client.send_text_message.return_value = "om_reply"

    handle_message(
        chat_id="oc_1",
        message_id="om_1",
        message_text="How do I deploy?",
        sender_id="ou_1",
    )

    lark_client.send_text_message.assert_called_once()
    call_kwargs = lark_client.send_text_message.call_args[1]
    assert call_kwargs["post_content"] == {"post": "content"}
    assert call_kwargs["root_id"] == "om_1"


def test_index_reply_skips_no_root_id(mock_dependencies) -> None:
    from src.pipeline import store

    index_reply(
        chat_id="oc_1",
        root_id="",
        reply_message_id="om_2",
        reply_content='{"text": "answer"}',
        reply_sender_id="ou_1",
        reply_create_time="1700000000000",
    )
    store.append_reply_to_qa.assert_not_called()


def test_index_reply_skips_root_not_question(mock_dependencies) -> None:
    from src.pipeline import lark_client, question_detector, store

    lark_client.get_message.return_value = {"content": '{"text": "Just a statement"}'}
    question_detector.is_question.return_value = False

    index_reply(
        chat_id="oc_1",
        root_id="om_root",
        reply_message_id="om_2",
        reply_content='{"text": "reply"}',
        reply_sender_id="ou_1",
        reply_create_time="1700000000000",
    )

    store.append_reply_to_qa.assert_not_called()


def test_index_reply_appends_reply(mock_dependencies) -> None:
    from src.pipeline import lark_client, question_detector, store

    lark_client.get_message.return_value = {"content": '{"text": "How do I deploy?"}'}
    question_detector.is_question.return_value = True

    index_reply(
        chat_id="oc_1",
        root_id="om_root",
        reply_message_id="om_2",
        reply_content='{"text": "Use the script"}',
        reply_sender_id="ou_alice",
        reply_create_time="1700000000000",
    )

    store.append_reply_to_qa.assert_called_once()
    call_kwargs = store.append_reply_to_qa.call_args.kwargs
    assert call_kwargs["question_text"] == "How do I deploy?"
    assert call_kwargs["new_reply_text"] == "Use the script"
    assert call_kwargs["chat_id"] == "oc_1"
    assert call_kwargs["root_id"] == "om_root"
    assert call_kwargs["answerer_open_id"] == "ou_alice"
