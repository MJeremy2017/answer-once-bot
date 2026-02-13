"""Vector store for Q&A: Chroma with metadata."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import uuid

from .config import CHROMA_PERSIST_DIR, SIMILARITY_THRESHOLD
from . import embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "answered_once_qa"


@dataclass
class QARecord:
    question_text: str
    answer_text: str
    answerer_name: str
    answer_time: datetime | str
    chat_id: str
    root_message_id: str
    thread_id: str
    answerer_open_id: str | None = None


_collection: Any = None


def _get_collection():
    global _collection
    if _collection is None:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path=str(CHROMA_PERSIST_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Answered-once Q&A"},
        )
    return _collection


def has_qa_for_root(root_message_id: str) -> bool:
    """Return True if we already have a Q&A record for this thread root."""
    if not root_message_id:
        return False
    coll = _get_collection()
    result = coll.get(where={"root_message_id": root_message_id}, limit=1)
    return bool(result and result.get("ids"))


def add_qa(
    question_text: str,
    answer_text: str,
    answerer_name: str,
    answer_time: datetime | str,
    chat_id: str,
    root_message_id: str,
    thread_id: str,
    answerer_open_id: str | None = None,
) -> None:
    """Index one Q&A pair."""
    coll = _get_collection()
    vec = embeddings.embed(question_text)
    id_ = str(uuid.uuid4())
    meta = {
        "answer_text": answer_text[:10000],
        "answerer_name": answerer_name,
        "answer_time": answer_time.isoformat() if isinstance(answer_time, datetime) else str(answer_time),
        "chat_id": chat_id,
        "root_message_id": root_message_id,
        "thread_id": thread_id,
    }
    if answerer_open_id:
        meta["answerer_open_id"] = answerer_open_id
    coll.add(
        ids=[id_],
        embeddings=[vec],
        documents=[question_text],
        metadatas=[meta],
    )


def find_similar_question(
    query_embedding: list[float],
    chat_id: str | None = None,
    top_k: int = 1,
    min_score: float | None = None,
) -> QARecord | None:
    """Return the best matching Q&A if score >= min_score, else None."""
    if min_score is None:
        min_score = SIMILARITY_THRESHOLD
    coll = _get_collection()
    n = coll.count()
    if n == 0:
        return None
    results = {"ids": [[]], "metadatas": [[]], "distances": [[]], "documents": [[]]}
    for where_filter in [{"chat_id": chat_id} if chat_id else None, None]:
        part = coll.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, n),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        if part["ids"] and part["ids"][0]:
            results = part
            break
    if not results["ids"] or not results["ids"][0]:
        return None
    dist = results["distances"][0][0]
    score = 1.0 - (dist * dist) / 2.0
    if score < min_score:
        return None
    meta = results["metadatas"][0][0]
    try:
        ts = datetime.fromisoformat(meta["answer_time"].replace("Z", "+00:00"))
    except Exception:
        ts = meta["answer_time"]
    return QARecord(
        question_text=results["documents"][0][0],
        answer_text=meta["answer_text"],
        answerer_name=meta["answerer_name"],
        answer_time=ts,
        chat_id=meta["chat_id"],
        root_message_id=meta["root_message_id"],
        thread_id=meta["thread_id"],
        answerer_open_id=meta.get("answerer_open_id") or None,
    )
