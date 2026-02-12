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

### 2. Permissions and behavior

**Current permissions (typical):**
- *Read and send messages in private and group chats*
- *Obtain group messages mentioning the bot*

With only these, Lark sends events **only when the bot is @mentioned**. So:
- The bot can **answer** when someone posts a question and @mentions the bot.
- The bot **cannot** record Q&A from other threads, because it never receives reply events where it isn’t mentioned.

**To record Q&A from all threads (recommended):**

1. In **Lark Developer Console** → your app → **Permissions**, add (if available for your app type):
   - **Obtain group chat messages** or **Receive all messages in group chats** (name may vary).
   This lets the bot receive every message in the group, including replies that don’t @mention it.

2. Set **`LARK_BOT_OPEN_ID`** in `.env` to your bot’s open_id, so the bot **only answers when @mentioned** but still processes all messages for indexing:
   - Send a test message that @mentions the bot and inspect the webhook event (or logs): `event.message.mentions[].id.open_id` for the bot is your `LARK_BOT_OPEN_ID`.
   - Or use the Lark API to get the bot’s open_id for the app.

3. Restart the bot. Result:
   - **Root message that @mentions the bot** → bot tries to answer (from DB or “don’t know”).
   - **Any reply in a thread** → bot may store that thread as Q&A (if root is a question and not already stored).

If you do **not** add “all group messages” and keep only “Obtain group messages mentioning the bot”, leave **`LARK_BOT_OPEN_ID`** empty. Then every event you receive is treated as “bot was mentioned” and the bot will answer when it’s a question; it still won’t receive other replies, so it can’t auto-record those Q&As.

### 3. Environment

Copy `.env.example` to `.env` and set:

- `LARK_APP_ID`, `LARK_APP_SECRET` (use quotes if the value has special characters: `LARK_APP_SECRET="your-secret"`)
- `LARK_BASE_URL`: `https://open.larksuite.com` (Lark) or `https://open.feishu.cn` (Feishu)
- Optional: `LARK_BOT_OPEN_ID`: bot’s open_id when using “all group messages” permission (so the bot only answers when @mentioned)
- **How to get `LARK_BOT_OPEN_ID`:** In the group, send a message that @mentions the bot. The server will log:  
  `LARK_BOT_OPEN_ID not set. From this @mention, candidate open_ids: ['ou_xxxx']` — use that `ou_xxxx` (if you @mentioned only the bot, it's the single value). Or inspect the webhook body: `event.message.mentions[].id.open_id` for the bot.
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
