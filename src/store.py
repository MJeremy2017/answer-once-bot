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
THREAD_REPLY_DELIMITER = "\n---\n"


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


def get_qa_by_root(root_message_id: str) -> QARecord | None:
    """Return the Q&A record for this thread root, or None."""
    if not root_message_id:
        return None
    coll = _get_collection()
    result = coll.get(
        where={"root_message_id": root_message_id},
        limit=1,
        include=["metadatas", "documents"],
    )
    if not result or not result.get("ids") or not result["ids"][0]:
        return None
    # get() returns flat lists: ids, metadatas, documents are each list of items (one per record)
    meta = result["metadatas"][0]
    doc = (result["documents"][0] if result.get("documents") and result["documents"] else "")
    return _metadata_to_record(meta, doc)


def delete_by_root(root_message_id: str) -> None:
    """Remove all Q&A records for this thread root (Chroma has no in-place update)."""
    if not root_message_id:
        return
    coll = _get_collection()
    coll.delete(where={"root_message_id": root_message_id})


def append_reply_to_qa(
    chat_id: str,
    root_id: str,
    question_text: str,
    new_reply_text: str,
    answerer_name: str,
    answer_time: datetime | str,
    answerer_open_id: str | None = None,
) -> None:
    """Append this reply to the Q&A for this root. Creates the record if first reply."""
    existing = get_qa_by_root(root_id)
    if existing is None:
        add_qa(
            question_text=question_text,
            answer_text=new_reply_text.strip(),
            answerer_name=answerer_name,
            answer_time=answer_time,
            chat_id=chat_id,
            root_message_id=root_id,
            thread_id=root_id,
            answerer_open_id=answerer_open_id,
        )
        return
    merged = (existing.answer_text.strip() + THREAD_REPLY_DELIMITER + new_reply_text.strip()).strip()
    delete_by_root(root_id)
    add_qa(
        question_text=existing.question_text,
        answer_text=merged,
        answerer_name=answerer_name,
        answer_time=answer_time,
        chat_id=chat_id,
        root_message_id=root_id,
        thread_id=root_id,
        answerer_open_id=answerer_open_id,
    )


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


def _dist_to_score(dist: float) -> float:
    """Convert Chroma L2 distance to a similarity-like score in [0, 1]."""
    return 1.0 - (dist * dist) / 2.0


def _metadata_to_record(meta: dict, document: str) -> QARecord:
    try:
        ts = datetime.fromisoformat(meta["answer_time"].replace("Z", "+00:00"))
    except Exception:
        ts = meta["answer_time"]
    return QARecord(
        question_text=document,
        answer_text=meta["answer_text"],
        answerer_name=meta["answerer_name"],
        answer_time=ts,
        chat_id=meta["chat_id"],
        root_message_id=meta["root_message_id"],
        thread_id=meta["thread_id"],
        answerer_open_id=meta.get("answerer_open_id") or None,
    )


def find_similar_questions(
    query_embedding: list[float],
    chat_id: str | None = None,
    top_k: int = 5,
    min_score: float | None = None,
) -> list[tuple[QARecord, float]]:
    """Return all Q&A records with score >= min_score, up to top_k, (record, score) pairs."""
    if min_score is None:
        min_score = SIMILARITY_THRESHOLD
    coll = _get_collection()
    n = coll.count()
    if n == 0:
        return []
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
        return []
    out: list[tuple[QARecord, float]] = []
    for i, dist in enumerate(results["distances"][0]):
        score = _dist_to_score(dist)
        if score < min_score:
            continue
        meta = results["metadatas"][0][i]
        doc = results["documents"][0][i] if results["documents"][0] else ""
        out.append((_metadata_to_record(meta, doc), score))
    return out


def pick_best_candidate(
    candidates: list[tuple[QARecord, float]],
    policy: str = "similarity",
) -> QARecord | None:
    """Pick one QARecord from candidates by policy. Returns None if candidates is empty."""
    if not candidates:
        return None
    if policy == "similarity":
        return max(candidates, key=lambda x: x[1])[0]
    if policy == "recency":
        def _recency_key(item: tuple[QARecord, float]) -> tuple[float, float]:
            rec, score = item
            t = rec.answer_time
            ts = t.timestamp() if isinstance(t, datetime) else 0.0
            return (ts, score)
        return max(candidates, key=_recency_key)[0]
    if policy == "longest":
        return max(candidates, key=lambda x: (len(x[0].answer_text), x[1]))[0]
    return candidates[0][0]


def find_similar_question(
    query_embedding: list[float],
    chat_id: str | None = None,
    top_k: int = 1,
    min_score: float | None = None,
) -> QARecord | None:
    """Return the best matching Q&A if score >= min_score, else None (backward compatible)."""
    candidates = find_similar_questions(
        query_embedding, chat_id=chat_id, top_k=max(1, top_k), min_score=min_score
    )
    if not candidates:
        return None
    return candidates[0][0]
