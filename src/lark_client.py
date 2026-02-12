"""Lark API client: tenant token and send message."""
import logging
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    GetMessageRequest,
    ListMessageRequest,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.core.const import FEISHU_DOMAIN, LARK_DOMAIN

from .config import (
    LARK_APP_ID,
    LARK_APP_SECRET,
    LARK_BASE_URL,
)

logger = logging.getLogger(__name__)

def _domain() -> str:
    """Return Lark API base URL (from lark_oapi.core.const)."""
    if "feishu.cn" in LARK_BASE_URL:
        return FEISHU_DOMAIN
    return LARK_DOMAIN


_client: lark.Client | None = None


def get_client() -> lark.Client:
    global _client
    if _client is None:
        _client = (
            lark.Client.builder()
            .app_id(LARK_APP_ID)
            .app_secret(LARK_APP_SECRET)
            .domain(_domain())
            .log_level(lark.LogLevel.WARNING)
            .build()
        )
    return _client


def send_text_message(
    chat_id: str,
    text: str,
    *,
    root_id: str | None = None,
) -> str | None:
    """Send a text message to a chat. If root_id is set, reply in that message's thread.
    Returns message_id on success, None on failure.
    """
    content = lark.JSON.marshal({"text": text})
    client = get_client()
    try:
        if root_id:
            # Use Reply Message API to reply in thread (CreateMessageRequestBody has no root_id in this SDK)
            body = (
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .reply_in_thread(True)
                .build()
            )
            request = (
                ReplyMessageRequest.builder()
                .message_id(root_id)
                .request_body(body)
                .build()
            )
            response = client.im.v1.message.reply(request)
        else:
            body_builder = (
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(content)
            )
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(body_builder.build())
                .build()
            )
            if hasattr(client.im.v1, "message") and hasattr(client.im.v1.message, "create"):
                response = client.im.v1.message.create(request)
            else:
                response = client.im.v1.chat.create(request)
        if not response.success():
            logger.error(
                "Lark send message failed: code=%s msg=%s",
                response.code,
                response.msg,
            )
            return None
        return response.data.message_id
    except Exception as e:
        logger.exception("Lark send message error: %s", e)
        return None


def list_messages(
    chat_id: str,
    *,
    page_size: int = 50,
) -> list[dict]:
    """List messages in a chat (paginated). Returns list of message dicts."""
    out: list[dict] = []
    page_token: str | None = None
    while True:
        req_builder = (
            ListMessageRequest.builder()
            .container_id_type("chat")
            .container_id(chat_id)
            .page_size(page_size)
        )
        if page_token:
            req_builder = req_builder.page_token(page_token)
        request = req_builder.build()
        try:
            response = get_client().im.v1.message.list(request)
        except Exception as e:
            logger.exception("List messages error: %s", e)
            break
        if not response.success():
            logger.error("List messages failed: code=%s msg=%s", response.code, response.msg)
            break
        items = response.data.items or []
        for i in items:
            body = getattr(i, "body", None) or {}
            content = getattr(body, "content", None) or ""
            sender = getattr(i, "sender", None) or {}
            sender_id = getattr(sender, "id", None) or getattr(sender, "open_id", None) or ""
            out.append({
                "message_id": getattr(i, "message_id", None) or "",
                "root_id": getattr(i, "root_id", None) or "",
                "parent_id": getattr(i, "parent_id", None) or "",
                "content": content,
                "sender_id": sender_id,
                "create_time": getattr(i, "create_time", None) or "",
            })
        page_token = getattr(response.data, "page_token", None) if response.data else None
        if not page_token or len(items) < page_size:
            break
    return out


def get_message(message_id: str) -> dict | None:
    """Fetch a message by ID. Returns dict with content, create_time, sender_id, chat_id, or None on failure."""
    try:
        request = GetMessageRequest.builder().message_id(message_id).build()
        response = get_client().im.v1.message.get(request)
        if not response.success() or not response.data:
            return None
        # Response may have data as message or data.items[0]
        msg = response.data
        if hasattr(msg, "items") and msg.items:
            msg = msg.items[0]
        content = getattr(getattr(msg, "body", None), "content", None) or ""
        create_time = getattr(msg, "create_time", None)
        sender = getattr(msg, "sender", None)
        sender_id = ""
        if sender:
            sender_id = getattr(sender, "open_id", None) or getattr(sender, "id", None) or ""
        chat_id = getattr(msg, "chat_id", None) or ""
        return {
            "content": content,
            "create_time": create_time,
            "sender_id": sender_id,
            "chat_id": chat_id,
        }
    except Exception as e:
        logger.exception("Get message error: %s", e)
        return None


def build_thread_link(chat_id: str, message_id: str) -> str:
    """Build a link to open the thread in Lark. Format may vary by tenant."""
    base = LARK_BASE_URL.replace("open.", "").rstrip("/")
    # Common pattern: messenger link to chat and message
    return f"{base}/messenger/thread/{chat_id}-{message_id}"
