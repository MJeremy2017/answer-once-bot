#!/usr/bin/env python3
"""Seed the Q&A index from a curated JSON file. Run from repo root."""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.store import add_qa

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Expected format: list of { "question": "", "answer": "", "answerer_name": "", "date": "YYYY-MM-DD", "chat_id": "", "root_message_id": "", "thread_id": "" }
# chat_id/root_message_id/thread_id can be placeholders if not from Lark.


def load_and_seed(faq_path: str | Path) -> int:
    path = Path(faq_path)
    if not path.exists():
        logger.error("File not found: %s", path)
        return 0
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", data.get("faq", []))
    count = 0
    for item in items:
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        if not q or not a:
            continue
        name = (item.get("answerer_name") or "Someone").strip()
        date_str = (item.get("date") or "").strip()
        try:
            ts = datetime.strptime(date_str[:10], "%Y-%m-%d") if date_str else datetime.utcnow()
        except ValueError:
            ts = datetime.utcnow()
        chat_id = (item.get("chat_id") or "seed").strip()
        root_id = (item.get("root_message_id") or item.get("thread_id") or "seed").strip()
        thread_id = (item.get("thread_id") or root_id).strip()
        add_qa(
            question_text=q,
            answer_text=a,
            answerer_name=name,
            answer_time=ts,
            chat_id=chat_id,
            root_message_id=root_id,
            thread_id=thread_id,
        )
        count += 1
        logger.info("Seeded: %s", q[:50])
    return count


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "data" / "faq_seed.json"
    n = load_and_seed(path)
    logger.info("Seeded %d Q&A pairs", n)


if __name__ == "__main__":
    main()
