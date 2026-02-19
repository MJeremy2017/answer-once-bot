"""LLM-based summarization of multiple Q&A candidates into one answer."""
import logging
from .config import LLM_BASE_URL, LLM_MODEL, OPENAI_API_KEY
from openai import OpenAI
from .store import QARecord

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant that summarizes past Q&A discussions.
Given a user's question and several relevant Q&A pairs from past discussions, produce a single concise, accurate summary answer.
Use only information present in the provided Q&A pairs. Do not invent or add information.
Write in a clear, direct style. Keep the summary brief (a few sentences or a short paragraph).
The "Answer" for a pair may be a long thread with multiple replies (e.g. acknowledgments, updates, and a final resolution). Summarize the key outcome or resolution rather than repeating early replies."""


def _build_user_prompt(user_question: str, candidates: list[tuple["QARecord", float]]) -> str:
    parts = [f"User asked: {user_question}", "", "Relevant Q&A pairs from past discussions:"]
    for i, (rec, _score) in enumerate(candidates, 1):
        parts.append(f"[{i}] Question: {rec.question_text}")
        parts.append(f"    Answer: {rec.answer_text}")
        parts.append("")
    parts.append(
        "Provide a concise summary answer that best addresses the user's question based only on the above. Do not invent information."
    )
    return "\n".join(parts)


def summarize_answer(
    user_question: str,
    candidates: list[tuple["QARecord", float]],
) -> str:
    """
    Call the LLM to produce a summarized answer from the user's question and the given Q&A candidates.
    Returns the model's reply text. Raises or returns a fallback message on missing key or API errors.
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; cannot summarize")
        raise ValueError("OPENAI_API_KEY is required for llm_summarize mode")
    if not candidates:
        return ""

    client_kwargs: dict = {"api_key": OPENAI_API_KEY}
    if LLM_BASE_URL:
        client_kwargs["base_url"] = LLM_BASE_URL
    client = OpenAI(**client_kwargs)

    user_prompt = _build_user_prompt(user_question, candidates)
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        return (content or "").strip()
    except Exception as e:
        logger.exception("LLM summarization failed: %s", e)
        raise
