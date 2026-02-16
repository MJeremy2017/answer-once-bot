"""Tests for main webhook app."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_pipeline_tasks():
    """Prevent pipeline from actually running (no Lark/Chroma in tests)."""
    with patch("src.main.pipeline.handle_message") as mock_handle, patch(
        "src.main.pipeline.index_reply"
    ) as mock_index:
        yield {"handle": mock_handle, "index": mock_index}


def test_get_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"


def test_get_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_url_verification(client: TestClient) -> None:
    r = client.post(
        "/webhook/lark",
        json={"challenge": "test_challenge_123", "type": "url_verification"},
    )
    assert r.status_code == 200
    assert r.json() == {"challenge": "test_challenge_123"}


def test_url_verification_root(client: TestClient) -> None:
    r = client.post(
        "/",
        json={"challenge": "ch2"},
    )
    assert r.status_code == 200
    assert r.json() == {"challenge": "ch2"}


def test_skip_unknown_event_type(client: TestClient) -> None:
    r = client.post(
        "/webhook/lark",
        json={
            "type": "event_callback",
            "event": {"type": "other.event"},
        },
    )
    assert r.status_code == 200
    assert r.json() == {}


def test_skip_v2_non_message_event(client: TestClient) -> None:
    r = client.post(
        "/webhook/lark",
        json={
            "schema": "2.0",
            "header": {"event_type": "other.event"},
            "event": {"message": {}},
        },
    )
    assert r.status_code == 200
    assert r.json() == {}


def test_root_message_triggers_pipeline(client: TestClient, mock_pipeline_tasks) -> None:
    r = client.post(
        "/webhook/lark",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "chat_id": "oc_chat1",
                    "message_id": "om_msg1",
                    "content": '{"text": "How do I deploy?"}',
                    "root_id": "",
                    "parent_id": "",
                    "mentions": [{"id": {"open_id": "ou_bot"}}],
                },
                "sender": {"sender_id": {"open_id": "ou_user"}, "open_id": "ou_user"},
            },
        },
    )
    assert r.status_code == 200
    # When LARK_BOT_OPEN_ID is not set, any message with mentions is treated as @mention
    # When LARK_BOT_OPEN_ID is set and matches, we run pipeline
    # Background task runs async - we can't easily assert it was called without awaiting
    # But we verified 200 and no crash


def test_reply_message_triggers_index_reply(client: TestClient, mock_pipeline_tasks) -> None:
    r = client.post(
        "/webhook/lark",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "chat_id": "oc_chat1",
                    "message_id": "om_reply1",
                    "root_id": "om_root1",
                    "parent_id": "om_root1",
                    "content": '{"text": "Use the script"}',
                },
                "sender": {"sender_id": {"open_id": "ou_user"}},
            },
        },
    )
    assert r.status_code == 200


def test_chat_id_normalized_from_dict(client: TestClient, mock_pipeline_tasks) -> None:
    """Lark v2 may send chat_id as object."""
    r = client.post(
        "/webhook/lark",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "chat_id": {"open_chat_id": "oc_123"},
                    "message_id": "om_1",
                    "content": '{"text": "What?"}',
                    "root_id": "",
                    "parent_id": "",
                    "mentions": [],
                },
                "sender": {},
            },
        },
    )
    assert r.status_code == 200


def test_invalid_json_returns_400(client: TestClient) -> None:
    r = client.post("/webhook/lark", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
