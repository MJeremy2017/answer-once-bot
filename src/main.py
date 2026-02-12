"""FastAPI app: Lark webhook endpoint (URL verification + message receive)."""
import json
import logging

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from . import pipeline
from .config import LARK_BOT_OPEN_ID

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Answered-Once Bot", version="0.1.0")


def _message_mentions_bot(mentions: list) -> bool:
    """True if the bot should respond: when LARK_BOT_OPEN_ID is set, only if message mentions that open_id; else True (we only receive @mention events)."""
    if not LARK_BOT_OPEN_ID:
        return True
    for m in mentions or []:
        id_obj = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
        if not id_obj:
            continue
        open_id = id_obj.get("open_id") if isinstance(id_obj, dict) else getattr(id_obj, "open_id", None)
        if open_id == LARK_BOT_OPEN_ID:
            return True
    return False


def _parse_message_content(content: str) -> str:
    """Extract plain text from Lark message content JSON."""
    try:
        data = json.loads(content)
        return (data.get("text") or "").strip()
    except (json.JSONDecodeError, TypeError):
        return ""


async def _handle_lark_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Handle Lark event subscription callback: URL verification and message events."""
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Invalid webhook body: %s", e)
        return Response(status_code=400)

    body_type = body.get("type")
    # Lark v2: schema + header + event; event type in header.event_type
    if body.get("schema") == "2.0" and "header" in body and "event" in body:
        event_type = (body.get("header") or {}).get("event_type")
        event = body.get("event", {})
    else:
        event = body.get("event", {})
        event_type = event.get("type")

    # URL verification
    if body_type == "url_verification" or (body.get("challenge") is not None and not body_type):
        return JSONResponse(content={"challenge": body.get("challenge", "")})

    # Event callback
    if body_type != "event_callback" and not event_type:
        logger.info("Lark webhook: skip (not event_callback and no event_type) body_type=%s event_type=%s", body_type, event_type)
        return JSONResponse(content={}, status_code=200)
    if event_type not in ("im.v1.message.receive_v1", "im.message.receive_v1"):
        logger.info("Lark webhook: skip (event_type not message receive) event_type=%s", event_type)
        return JSONResponse(content={}, status_code=200)

    message = event.get("message", {})
    sender = event.get("sender", {})
    raw_chat_id = message.get("chat_id")
    # Lark v2 may send chat_id as object e.g. {"open_chat_id": "oc_xxx"}
    if isinstance(raw_chat_id, dict):
        chat_id = raw_chat_id.get("open_chat_id") or raw_chat_id.get("chat_id") or ""
    else:
        chat_id = raw_chat_id or ""
    message_id = message.get("message_id")
    root_id = message.get("root_id") or ""
    parent_id = message.get("parent_id") or ""
    content = message.get("content", "{}")
    sender_id = (sender.get("sender_id", {}) or {}).get("open_id") or sender.get("open_id") or ""

    if not chat_id or not message_id:
        logger.info("Lark webhook: skip (missing chat_id or message_id) chat_id=%s message_id=%s", chat_id, message_id)
        return JSONResponse(content={}, status_code=200)

    message_text = _parse_message_content(content)
    create_time = message.get("create_time") or ""
    mentions = message.get("mentions") or []

    # Normalize message_id / root_id if sent as object (e.g. {"message_id": "om_xxx"})
    if isinstance(message_id, dict):
        message_id = message_id.get("message_id") or message_id.get("open_message_id") or ""
    if isinstance(root_id, dict):
        root_id = root_id.get("message_id") or root_id.get("open_message_id") or ""
    if isinstance(parent_id, dict):
        parent_id = parent_id.get("message_id") or parent_id.get("open_message_id") or ""

    logger.info(
        "Lark message: chat_id=%s message_id=%s root_id=%s parent_id=%s text=%r",
        chat_id, message_id, root_id or None, parent_id or None, (message_text[:60] + "..." if len(message_text) > 60 else message_text),
    )

    if root_id or parent_id:
        # Reply in a thread: try to record this Q&A (root question + this reply) into the store
        logger.info("Lark: reply in thread -> index_reply")
        background_tasks.add_task(
            _run_index_reply,
            chat_id=chat_id,
            root_id=root_id or parent_id,
            reply_message_id=message_id,
            reply_content=content,
            reply_sender_id=sender_id,
            reply_create_time=create_time,
        )
        return JSONResponse(content={}, status_code=200)

    # Root-level message: answer only when the bot is @mentioned
    if not _message_mentions_bot(mentions):
        logger.info("Lark: root message but bot not @mentioned -> skip")
        return JSONResponse(content={}, status_code=200)
    logger.info("Lark: root message @mentioned -> pipeline (answer)")
    if not LARK_BOT_OPEN_ID and mentions:
        open_ids = []
        for m in mentions or []:
            id_obj = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
            if id_obj:
                oid = id_obj.get("open_id") if isinstance(id_obj, dict) else getattr(id_obj, "open_id", None)
                if oid:
                    open_ids.append(oid)
        if open_ids:
            logger.info(
                "LARK_BOT_OPEN_ID not set. From this @mention, candidate open_ids: %s — set one in .env to only answer when @mentioned.",
                open_ids,
            )
    background_tasks.add_task(
        _run_pipeline,
        chat_id=chat_id,
        message_id=message_id,
        message_text=message_text,
        sender_id=sender_id,
    )
    return JSONResponse(content={}, status_code=200)


def _run_pipeline(
    chat_id: str,
    message_id: str,
    message_text: str,
    sender_id: str,
) -> None:
    try:
        pipeline.handle_message(
            chat_id=chat_id,
            message_id=message_id,
            message_text=message_text,
            sender_id=sender_id,
        )
    except Exception as e:
        logger.exception("Pipeline error: %s", e)


def _run_index_reply(
    chat_id: str,
    root_id: str,
    reply_message_id: str,
    reply_content: str,
    reply_sender_id: str,
    reply_create_time: str,
) -> None:
    try:
        pipeline.try_index_reply(
            chat_id=chat_id,
            root_id=root_id,
            reply_message_id=reply_message_id,
            reply_content=reply_content,
            reply_sender_id=reply_sender_id,
            reply_create_time=reply_create_time,
        )
    except Exception as e:
        logger.exception("Index reply error: %s", e)


@app.post("/webhook/lark")
async def lark_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Lark webhook endpoint at /webhook/lark."""
    return await _handle_lark_webhook(request, background_tasks)


@app.post("/")
async def lark_webhook_root(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Lark webhook endpoint at root (/) - supports both paths."""
    return await _handle_lark_webhook(request, background_tasks)


@app.get("/")
async def root() -> Response:
    """Root GET (e.g. health check)."""
    return JSONResponse(content={"status": "ok", "message": "Answered-Once Bot. Use POST for webhook."})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
