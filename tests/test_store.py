"""Tests for store."""
from datetime import datetime
from unittest.mock import patch

import pytest

from src.store import QARecord, add_qa, find_similar_question, has_qa_for_root


# All-MiniLM-L6-v2 outputs 384-dim vectors; use simple placeholder
FAKE_EMBEDDING = [0.1] * 384


@pytest.fixture
def mock_embeddings(monkeypatch):
    """Mock embeddings to avoid loading sentence-transformers."""
    def fake_embed(text: str):
        return FAKE_EMBEDDING.copy()

    import src.store as store_mod

    monkeypatch.setattr(store_mod.embeddings, "embed", fake_embed)


@pytest.fixture
def store_with_qa(mock_embeddings, temp_chroma_dir, reset_store_collection):
    """Add one Q&A to the store for find tests."""
    add_qa(
        question_text="How do I deploy?",
        answer_text="Use the deploy script.",
        answerer_name="Alice",
        answer_time=datetime(2024, 2, 13),
        chat_id="oc_chat1",
        root_message_id="om_root1",
        thread_id="om_root1",
        answerer_open_id="ou_alice",
    )
    yield


def test_has_qa_for_root_empty(reset_store_collection, temp_chroma_dir) -> None:
    assert has_qa_for_root("om_any") is False
    assert has_qa_for_root("") is False


def test_has_qa_for_root_after_add(mock_embeddings, temp_chroma_dir, reset_store_collection) -> None:
    add_qa(
        question_text="Q?",
        answer_text="A",
        answerer_name="X",
        answer_time=datetime.now(),
        chat_id="oc_1",
        root_message_id="om_root1",
        thread_id="om_root1",
    )
    assert has_qa_for_root("om_root1") is True
    assert has_qa_for_root("om_other") is False


def test_find_similar_question_empty_store(mock_embeddings, temp_chroma_dir, reset_store_collection) -> None:
    assert find_similar_question(FAKE_EMBEDDING, chat_id="oc_chat1") is None


def test_find_similar_question_finds_match(
    mock_embeddings, store_with_qa, temp_chroma_dir, reset_store_collection
) -> None:
    match = find_similar_question(FAKE_EMBEDDING, chat_id="oc_chat1")
    assert match is not None
    assert isinstance(match, QARecord)
    assert match.question_text == "How do I deploy?"
    assert match.answer_text == "Use the deploy script."
    assert match.answerer_name == "Alice"
    assert match.chat_id == "oc_chat1"
    assert match.root_message_id == "om_root1"
    assert match.answerer_open_id == "ou_alice"


def test_find_similar_question_min_score_too_high(
    mock_embeddings, store_with_qa, temp_chroma_dir, reset_store_collection
) -> None:
    # With identical embeddings score=1.0; min_score > 1 => no match
    match = find_similar_question(FAKE_EMBEDDING, chat_id="oc_chat1", min_score=1.001)
    assert match is None
