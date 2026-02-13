"""Heuristic question detection for MVP."""
import re

# If text contains any of these words (as whole word), treat as question
QUESTION_WORDS = re.compile(r"\b(how|what|when|where|why|who|which)\b", re.IGNORECASE)

# Extra phrases not covered by question words (who, which, can/could, etc.)
QUESTION_PHRASES = [
    r"\bcan\s+(?:we|someone)\b",
    r"\bcould\s+(?:we|you)\b",
    r"\bdoes\s+anyone\b",
    r"\bis\s+there\s+(?:a|an)\b",
]
QUESTION_PATTERN = re.compile("|".join(f"({p})" for p in QUESTION_PHRASES), re.IGNORECASE)


def is_question(text: str) -> bool:
    """Return True if the text looks like a question (heuristic)."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    if QUESTION_WORDS.search(t):
        return True
    if QUESTION_PATTERN.search(t):
        return True
    return False
