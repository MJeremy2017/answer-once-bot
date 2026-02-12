"""Heuristic question detection for MVP."""
import re

# Phrases that often start or contain a question (case-insensitive)
QUESTION_PHRASES = [
    r"\bhow\s+do\s+(?:we|i|you)\b",
    r"\bhow\s+can\s+(?:we|i|someone)\b",
    r"\bwhere\s+do\s+(?:we|i|you)\b",
    r"\bwhat\s+is\s+(?:the|a|an)\b",
    r"\bwhat\s+are\s+(?:the|they)\b",
    r"\bcan\s+someone\b",
    r"\bwho\s+can\b",
    r"\bdoes\s+anyone\b",
    r"\bis\s+there\s+(?:a|an)\b",
    r"\bwhich\s+(?:way|tool|process)\b",
    r"\bwhy\s+do\s+(?:we|i)\b",
    r"\bwhen\s+do\s+(?:we|i)\b",
]
QUESTION_PATTERN = re.compile("|".join(f"({p})" for p in QUESTION_PHRASES), re.IGNORECASE)


def is_question(text: str) -> bool:
    """Return True if the text looks like a question (heuristic)."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False
    # Ends with ?
    if t.endswith("?"):
        return True
    # Starts with or contains question phrase
    if QUESTION_PATTERN.search(t):
        return True
    return False
