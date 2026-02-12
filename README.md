# Answered-Once Bot (MVP)

A Lark bot that detects when someone asks a question that was already answered in the channel and replies with who answered it, when, and a short summary with a link to the original thread.

## What it does

1. User asks a question in a channel.
2. The bot detects that it is a **question** and **semantically similar** to a previously answered question.
3. The bot replies (in thread) with: who answered before, date, summary, and "View original thread" link.

## Setup

### 1. Lark app

- Create a [Lark/Feishu app](https://open.larksuite.com/app) (Custom App).
- **Credentials:** Note App ID and App Secret.
- **Permissions:** Enable "Receive messages" and "Send messages" for the bot; enable "Get chat history" (or equivalent) if you will use the backfill script.
- **Event subscription:** Subscribe to `im.message.receive_v1`. Set **Request URL** to your webhook (e.g. `https://your-host/webhook/lark`). Do not enable encryption (Encrypt Key empty).
- **URL verification:** When you save the Request URL, Lark sends a `url_verification` event; the server responds with the challenge and passes verification.

### 2. Lark message events

With permission "Obtain group messages mentioning the bot", Lark may only send message events when the bot is **@mentioned**. Try asking your question while @mentioning the bot, e.g.:

> @AnsweredOnceBot How do we request production access?

To receive **all** messages in a group (without @mention), add the permission "Obtain group chat messages" or similar in the Lark app settings, if available for your app type.

### 3. Environment

Copy `.env.example` to `.env` and set:

- `LARK_APP_ID`, `LARK_APP_SECRET` (use quotes if the value has special characters: `LARK_APP_SECRET="your-secret"`)
- `LARK_BASE_URL`: `https://open.larksuite.com` (Lark) or `https://open.feishu.cn` (Feishu)
- `SIMILARITY_THRESHOLD`: e.g. `0.78` (tune to avoid false positives/negatives)
- Optional: `ANSWERED_ONCE_CHAT_IDS`: comma-separated chat IDs to limit indexing/matching to those channels

### 4. Install and run

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Seed the index** (curated FAQ, no Lark history needed). For same-channel matching, set `chat_id` in `data/faq_seed.json` to your test chat ID (get it from the chat URL or API).

```bash
python scripts/seed_faq.py data/faq_seed.json
```

Or **backfill from channel history** (set `ANSWERED_ONCE_CHAT_IDS` to your chat IDs):

```bash
python scripts/backfill.py
```

**Start the webhook server:**

```bash
python run.py
```

Server listens on `http://0.0.0.0:8000`. Use a tunnel (e.g. ngrok) for local dev and set the Lark Request URL to `https://your-tunnel/webhook/lark`.

## Project layout

- `src/` – app code
  - `main.py` – FastAPI app, `/webhook/lark` and `/health`
  - `lark_client.py` – Lark API (send message, list messages, thread link)
  - `question_detector.py` – heuristic question detection
  - `embeddings.py` – sentence-transformers embedding
  - `store.py` – Chroma vector store and Q&A index
  - `formatter.py` – reply text format
  - `pipeline.py` – handle message: question check → embed → match → format → send
- `scripts/` – `seed_faq.py`, `backfill.py`
- `data/` – optional `faq_seed.json` and Chroma DB persistence

## Success criteria (MVP)

- In a test channel, posting a question that is semantically similar to an indexed Q&A gets a reply with "answered before by X on date", summary, and "View original thread".
- No reply when the message is not a question or when there is no similar question above the threshold.
- Webhook passes URL verification and returns 200 for events without crashing.
