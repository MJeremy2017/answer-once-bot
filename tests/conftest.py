"""Pytest fixtures and configuration."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def reset_store_collection():
    """Reset the store's global collection so tests use fresh Chroma."""
    import src.store as store_mod

    old = getattr(store_mod, "_collection", None)
    store_mod._collection = None
    yield
    store_mod._collection = old


@pytest.fixture
def temp_chroma_dir(monkeypatch):
    """Use a temporary directory for Chroma in tests."""
    tmp = tempfile.mkdtemp(prefix="answer_once_test_chroma_")
    try:
        monkeypatch.setattr("src.config.CHROMA_PERSIST_DIR", Path(tmp))
        monkeypatch.setattr("src.store.CHROMA_PERSIST_DIR", Path(tmp))
        yield Path(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_env(monkeypatch):
    """Set minimal env for tests (no real Lark credentials)."""
    monkeypatch.setenv("LARK_APP_ID", "test_app_id")
    monkeypatch.setenv("LARK_APP_SECRET", "test_app_secret")
    monkeypatch.setenv("LARK_BASE_URL", "https://open.larksuite.com")
    monkeypatch.delenv("LARK_BOT_OPEN_ID", raising=False)
    monkeypatch.delenv("ANSWERED_ONCE_CHAT_IDS", raising=False)
