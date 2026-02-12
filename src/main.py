"""FastAPI app: Lark webhook endpoint (URL verification + message receive)."""
import json
import logging

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from . import pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Answered-Once Bot", version="0.1.0")


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
        return JSONResponse(content={}, status_code=200)
    if event_type not in ("im.v1.message.receive_v1", "im.message.receive_v1"):
        return JSONResponse(content={}, status_code=200)

    message = event.get("message", {})
    sender = event.get("sender", {})
    chat_id = message.get("chat_id")
    message_id = message.get("message_id")
    root_id = message.get("root_id") or ""
    parent_id = message.get("parent_id") or ""
    content = message.get("content", "{}")
    sender_id = (sender.get("sender_id", {}) or {}).get("open_id") or sender.get("open_id") or ""

    if not chat_id or not message_id:
        return JSONResponse(content={}, status_code=200)

    message_text = _parse_message_content(content)
    if root_id or parent_id:
        return JSONResponse(content={}, status_code=200)

    # Run pipeline in background so we return 200 quickly to Lark
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
