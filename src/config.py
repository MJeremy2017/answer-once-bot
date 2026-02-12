"""Configuration from environment."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _str(value: str | None) -> str:
    return (value or "").strip()


def _float(value: str | None, default: float) -> float:
    try:
        return float((value or "").strip()) if value else default
    except ValueError:
        return default


# Lark
LARK_APP_ID = _str(os.getenv("LARK_APP_ID"))
LARK_APP_SECRET = _str(os.getenv("LARK_APP_SECRET"))
LARK_BASE_URL = _str(os.getenv("LARK_BASE_URL")) or "https://open.larksuite.com"

# Optional: limit to specific chats (comma-separated)
_chat_ids = _str(os.getenv("ANSWERED_ONCE_CHAT_IDS"))
ANSWERED_ONCE_CHAT_IDS: list[str] = [x.strip() for x in _chat_ids.split(",") if x.strip()]

# Similarity
SIMILARITY_THRESHOLD = _float(os.getenv("SIMILARITY_THRESHOLD"), 0.78)

# Chroma
CHROMA_PERSIST_DIR = Path(_str(os.getenv("CHROMA_PERSIST_DIR")) or "./data/chroma")
