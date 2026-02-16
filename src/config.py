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


def _int(value: str | None, default: int) -> int:
    try:
        return int((value or "").strip()) if value else default
    except ValueError:
        return default


# Lark
LARK_APP_ID = _str(os.getenv("LARK_APP_ID"))
LARK_APP_SECRET = _str(os.getenv("LARK_APP_SECRET"))
LARK_BASE_URL = _str(os.getenv("LARK_BASE_URL")) or "https://open.larksuite.com"
# When set: only answer when the message @mentions the bot (use with "all messages" permission).
# Get it from a message event where the bot is mentioned: message.mentions[].id.open_id for the bot.
LARK_BOT_OPEN_ID = _str(os.getenv("LARK_BOT_OPEN_ID"))

# Optional: limit to specific chats (comma-separated)
_chat_ids = _str(os.getenv("ANSWERED_ONCE_CHAT_IDS"))
ANSWERED_ONCE_CHAT_IDS: list[str] = [x.strip() for x in _chat_ids.split(",") if x.strip()]

# Similarity
SIMILARITY_THRESHOLD = _float(os.getenv("SIMILARITY_THRESHOLD"), 0.78)

# Answer mode: top_1 (single best match) or llm (top-k + LLM summary)
ANSWER_MODE = _str(os.getenv("ANSWER_MODE")) or "top_1"
TOP_K_CANDIDATES = max(1, _int(os.getenv("TOP_K_CANDIDATES"), 5))
BEST_ANSWER_POLICY = _str(os.getenv("BEST_ANSWER_POLICY")) or "similarity"  # similarity | recency | longest

# LLM (for llm_summarize mode)
OPENAI_API_KEY = _str(os.getenv("OPENAI_API_KEY")) or _str(os.getenv("LLM_API_KEY"))
LLM_MODEL = _str(os.getenv("LLM_MODEL")) or "gpt-4o-mini"
LLM_BASE_URL = _str(os.getenv("LLM_BASE_URL"))  # optional, for non-OpenAI endpoints

# Chroma
CHROMA_PERSIST_DIR = Path(_str(os.getenv("CHROMA_PERSIST_DIR")) or "./data/chroma")
