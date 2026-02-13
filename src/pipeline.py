"""Pipeline: question check -> embed -> match -> format -> send; and index Q&A from replies."""
import json
import logging
from datetime import datetime

from . import embeddings
from . import store
from . import formatter
from . import lark_client
from . import question_detector
from .config import ANSWERED_ONCE_CHAT_IDS

logger = logging.getLogger(__name__)

DONT_KNOW_REPLY = "I don't have an answer for this question yet."


def handle_message(
    chat_id: str,
    message_id: str,
    message_text: str,
    sender_id: str,
) -> None:
    """Handle a root-level message: if it's a question, reply with a match or 'don't know'."""
    if not message_text or not message_text.strip():
        logger.info("handle_message: skip (empty text) message_id=%s", message_id)
        return
    if not question_detector.is_question(message_text):
        logger.info("handle_message: skip (not a question) message_id=%s text=%r", message_id, message_text[:50])
        return
    if ANSWERED_ONCE_CHAT_IDS and chat_id not in ANSWERED_ONCE_CHAT_IDS:
        logger.info("handle_message: skip (chat_id not in ANSWERED_ONCE_CHAT_IDS) chat_id=%s", chat_id)
        return
    query_embedding = embeddings.embed(message_text)
    match = store.find_similar_question(query_embedding, chat_id=chat_id)
    if match:
        thread_link = lark_client.build_thread_link(match.chat_id, match.root_message_id)
        summary = _truncate_summary(match.answer_text, max_chars=500)
        post_content = formatter.build_post_content(
            answer_time=match.answer_time,
            answer_summary=summary,
            thread_link=thread_link,
            answerer_open_id=match.answerer_open_id,
        )
        reply_text = formatter.format_reply(
            answerer_name=match.answerer_name,
            answer_time=match.answer_time,
            answer_summary=summary,
            thread_link=thread_link,
        )
        sent_id = lark_client.send_text_message(
            chat_id,
            reply_text,
            root_id=message_id,
            post_content=post_content,
        )
    else:
        reply_text = DONT_KNOW_REPLY
        sent_id = lark_client.send_text_message(chat_id, reply_text, root_id=message_id)
    if sent_id:
        logger.info("Replied to message_id=%s sent_id=%s", message_id, sent_id)
    else:
        logger.warning("Failed to send reply for message_id=%s", message_id)


def index_reply(
    chat_id: str,
    root_id: str,
    reply_message_id: str,
    reply_content: str,
    reply_sender_id: str,
    reply_create_time: str,
) -> None:
    """When a reply is posted, if the root is a question and not yet indexed, add Q&A to the store."""
    if not root_id or not reply_content:
        logger.info("index_reply: skip (no root_id or empty reply) root_id=%s", root_id)
        return
    if store.has_qa_for_root(root_id):
        logger.info("index_reply: skip (already has Q&A for root) root_id=%s", root_id)
        return
    root_msg = lark_client.get_message(root_id)
    if not root_msg:
        logger.warning("index_reply: skip (could not fetch root message) root_id=%s", root_id)
        return
    question_text = _parse_content(root_msg.get("content") or "{}")
    if not question_detector.is_question(question_text):
        logger.info("index_reply: skip (root is not a question) root_id=%s text=%r", root_id, question_text[:50])
        return
    answer_text = _parse_content(reply_content)
    if not answer_text.strip():
        logger.info("index_reply: skip (reply has no text) root_id=%s", root_id)
        return
    try:
        ts = datetime.utcfromtimestamp(int(reply_create_time) / 1000)
    except (TypeError, ValueError):
        ts = datetime.utcnow()
    answerer_name = f"User ({reply_sender_id[:12]}...)" if len(str(reply_sender_id)) > 12 else f"User ({reply_sender_id})"
    store.add_qa(
        question_text=question_text,
        answer_text=answer_text,
        answerer_name=answerer_name,
        answer_time=ts,
        chat_id=chat_id,
        root_message_id=root_id,
        thread_id=root_id,
        answerer_open_id=reply_sender_id or None,
    )
    logger.info("Indexed Q&A for root_id=%s", root_id)


def _parse_content(content: str) -> str:
    try:
        data = json.loads(content) if isinstance(content, str) else {}
        return (data.get("text") or "").strip()
    except (json.JSONDecodeError, TypeError):
        return ""


def _truncate_summary(text: str, max_chars: int = 500) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rsplit(" ", 1)[0] + "..."
