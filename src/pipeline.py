"""Pipeline: question check -> embed -> match -> format -> send."""
import logging

from . import embeddings
from . import store
from . import formatter
from . import lark_client
from . import question_detector
from .config import ANSWERED_ONCE_CHAT_IDS

logger = logging.getLogger(__name__)


def handle_message(
    chat_id: str,
    message_id: str,
    message_text: str,
    sender_id: str,
) -> None:
    """Handle an incoming channel message: if it's a question and we have a match, reply."""
    if not message_text or not message_text.strip():
        return
    if not question_detector.is_question(message_text):
        return
    if ANSWERED_ONCE_CHAT_IDS and chat_id not in ANSWERED_ONCE_CHAT_IDS:
        return
    query_embedding = embeddings.embed(message_text)
    match = store.find_similar_question(query_embedding, chat_id=chat_id)
    if not match:
        return
    thread_link = lark_client.build_thread_link(match.chat_id, match.root_message_id)
    summary = _truncate_summary(match.answer_text, max_chars=500)
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
    )
    if sent_id:
        logger.info(
            "Replied to message_id=%s with match root=%s, sent_id=%s",
            message_id,
            match.root_message_id,
            sent_id,
        )
    else:
        logger.warning("Failed to send reply for message_id=%s", message_id)


def _truncate_summary(text: str, max_chars: int = 500) -> str:
    """Truncate answer for summary, one line preferred."""
    if not text:
        return ""
    text = text.strip().replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rsplit(" ", 1)[0] + "..."
