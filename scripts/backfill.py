#!/usr/bin/env python3
"""Backfill Q&A index from Lark channel history. Run from repo root with env set."""
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add project root so we can import src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ANSWERED_ONCE_CHAT_IDS, LARK_APP_ID
from src.lark_client import list_messages
from src.question_detector import is_question
from src.store import add_qa

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_content(content: str) -> str:
    try:
        data = json.loads(content) if isinstance(content, str) else {}
        return (data.get("text") or "").strip()
    except (json.JSONDecodeError, TypeError):
        return ""


def backfill_chat(chat_id: str) -> int:
    """Index Q&A from one chat. Returns number of Q&A pairs indexed."""
    messages = list_messages(chat_id, page_size=50)
    if not messages:
        logger.warning("No messages in chat %s", chat_id)
        return 0
    # Group by root_id: roots have root_id empty; replies have root_id set
    by_root: dict[str, list[dict]] = defaultdict(list)
    roots: dict[str, dict] = {}
    for m in messages:
        root_id = (m.get("root_id") or "").strip()
        if not root_id:
            roots[m.get("message_id") or ""] = m
        else:
            by_root[root_id].append(m)
    # Sort replies by create_time so we take first reply
    for root_id in by_root:
        by_root[root_id].sort(key=lambda x: int(x.get("create_time") or 0))
    count = 0
    for root_msg_id, root in roots.items():
        if not root_msg_id:
            continue
        content = _parse_content(root.get("content") or "{}")
        if not is_question(content):
            continue
        replies = by_root.get(root_msg_id, [])
        if not replies:
            continue
        first_reply = replies[0]
        answer_text = _parse_content(first_reply.get("content") or "{}")
        if not answer_text:
            continue
        sender_id = first_reply.get("sender_id") or "unknown"
        create_time = first_reply.get("create_time") or ""
        try:
            ts = datetime.utcfromtimestamp(int(create_time) / 1000) if create_time else datetime.utcnow()
        except Exception:
            ts = datetime.utcnow()
        # Use a display name: we don't fetch user name in MVP; use "User (open_id)" or "Someone"
        answerer_name = f"User ({sender_id[:12]}...)" if len(str(sender_id)) > 12 else f"User ({sender_id})"
        add_qa(
            question_text=content,
            answer_text=answer_text,
            answerer_name=answerer_name,
            answer_time=ts,
            chat_id=chat_id,
            root_message_id=root_msg_id,
            thread_id=root_msg_id,
        )
        count += 1
        logger.info("Indexed Q&A: %s -> %s", content[:50], answer_text[:50])
    return count


def main() -> None:
    if not LARK_APP_ID:
        logger.error("Set LARK_APP_ID (and LARK_APP_SECRET) in env")
        sys.exit(1)
    chat_ids = ANSWERED_ONCE_CHAT_IDS
    if not chat_ids:
        logger.error("Set ANSWERED_ONCE_CHAT_IDS (comma-separated chat IDs) in env to backfill")
        sys.exit(1)
    total = 0
    for cid in chat_ids:
        logger.info("Backfilling chat %s", cid)
        total += backfill_chat(cid)
    logger.info("Backfill done: %d Q&A pairs indexed", total)


if __name__ == "__main__":
    main()
