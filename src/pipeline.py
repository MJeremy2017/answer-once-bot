"""Pipeline: question check -> embed -> match -> format -> send; and index Q&A from replies."""
import json
import logging
from datetime import datetime

from . import embeddings
from . import store
from . import formatter
from . import lark_client
from . import question_detector
from .config import (
    ANSWER_MODE,
    ANSWERED_ONCE_CHAT_IDS,
    BEST_ANSWER_POLICY,
    TOP_K_CANDIDATES,
)

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

    if ANSWER_MODE == "llm_summarize":
        _handle_message_llm_summarize(chat_id, message_id, message_text, query_embedding)
    else:
        _handle_message_top_1(chat_id, message_id, message_text, query_embedding)


def _handle_message_top_1(chat_id: str, message_id: str, message_text: str, query_embedding: list[float]) -> None:
    """top_1 mode: single best match; full thread sent to LLM for summary when possible."""
    candidates = store.find_similar_questions(
        query_embedding, chat_id=chat_id, top_k=1
    )
    if not candidates:
        sent_id = lark_client.send_text_message(chat_id, DONT_KNOW_REPLY, root_id=message_id)
    else:
        match, _ = candidates[0]
        thread_link = lark_client.build_thread_link(match.chat_id, match.root_message_id)
        try:
            from . import answer_summarizer
            summary = answer_summarizer.summarize_answer(message_text, candidates)
        except (ValueError, ImportError) as e:
            logger.warning("LLM summarization skipped (%s), truncating", e)
            summary = _truncate_summary(match.answer_text, max_chars=500)
        post_content = formatter.build_post_content(
            answer_time=match.answer_time,
            answer_summary=_truncate_summary(summary, max_chars=500),
            thread_link=thread_link,
            answerer_open_id=match.answerer_open_id,
        )
        reply_text = formatter.format_reply(
            answerer_name=match.answerer_name,
            answer_time=match.answer_time,
            answer_summary=_truncate_summary(summary, max_chars=500),
            thread_link=thread_link,
        )
        sent_id = lark_client.send_text_message(
            chat_id,
            reply_text,
            root_id=message_id,
            post_content=post_content,
        )
    if sent_id:
        logger.info("Replied to message_id=%s sent_id=%s", message_id, sent_id)
    else:
        logger.warning("Failed to send reply for message_id=%s", message_id)


def _handle_message_llm_summarize(
    chat_id: str,
    message_id: str,
    message_text: str,
    query_embedding: list[float],
) -> None:
    """llm_summarize mode: top-k candidates, LLM summary, source links."""
    from . import answer_summarizer

    candidates = store.find_similar_questions(
        query_embedding,
        chat_id=chat_id,
        top_k=TOP_K_CANDIDATES,
    )
    if not candidates:
        sent_id = lark_client.send_text_message(chat_id, DONT_KNOW_REPLY, root_id=message_id)
    else:
        try:
            summary = answer_summarizer.summarize_answer(message_text, candidates)
        except (ValueError, ImportError) as e:
            logger.warning("LLM summarization skipped (%s), falling back to top-1", e)
            best = store.pick_best_candidate(candidates, policy=BEST_ANSWER_POLICY)
            if best:
                thread_link = lark_client.build_thread_link(best.chat_id, best.root_message_id)
                summary = _truncate_summary(best.answer_text, max_chars=500)
                post_content = formatter.build_post_content(
                    answer_time=best.answer_time,
                    answer_summary=summary,
                    thread_link=thread_link,
                    answerer_open_id=best.answerer_open_id,
                )
                reply_text = formatter.format_reply(
                    answerer_name=best.answerer_name,
                    answer_time=best.answer_time,
                    answer_summary=summary,
                    thread_link=thread_link,
                )
                sent_id = lark_client.send_text_message(
                    chat_id, reply_text, root_id=message_id, post_content=post_content
                )
            else:
                sent_id = lark_client.send_text_message(chat_id, DONT_KNOW_REPLY, root_id=message_id)
        except Exception as e:
            logger.exception("LLM summarization failed: %s", e)
            sent_id = lark_client.send_text_message(chat_id, DONT_KNOW_REPLY, root_id=message_id)
        else:
            source_links = [
                lark_client.build_thread_link(rec.chat_id, rec.root_message_id)
                for rec, _ in candidates
            ]
            summary_truncated = _truncate_summary(summary, max_chars=500)
            post_content = formatter.build_post_content(
                answer_time="various",
                answer_summary=summary_truncated,
                thread_link=source_links[0] if source_links else "",
                answerer_open_id=None,
                source_links=source_links,
            )
            reply_text = formatter.format_reply(
                answerer_name="Past discussions",
                answer_time="various",
                answer_summary=summary_truncated,
                thread_link=source_links[0] if source_links else "",
                source_links=source_links,
            )
            sent_id = lark_client.send_text_message(
                chat_id,
                reply_text,
                root_id=message_id,
                post_content=post_content,
            )
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
    """When a reply is posted, append it to the Q&A for this root (create if first reply)."""
    if not root_id or not reply_content:
        logger.info("index_reply: skip (no root_id or empty reply) root_id=%s", root_id)
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
    store.append_reply_to_qa(
        chat_id=chat_id,
        root_id=root_id,
        question_text=question_text,
        new_reply_text=answer_text,
        answerer_name=answerer_name,
        answer_time=ts,
        answerer_open_id=reply_sender_id or None,
    )
    logger.info("Appended reply to Q&A for root_id=%s", root_id)


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
