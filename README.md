# AI Call Analyzer

Webhook-driven pay-per-call QA app. When Moja AI fires a webhook on call
completion, this service downloads the recording, transcribes it locally with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (splitting stereo
channels for free caller/agent labels), scores it against a per-buyer rubric via
Claude, saves it to a database, and sends a Telegram alert with timestamped
evidence.

## Quick start

```bash
# 1. Create venv & install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# edit .env — see "Required .env values" below

# 3. Run
uvicorn app.main:app --reload

# 4. Verify
curl http://localhost:8000/healthz
# → {"status":"ok"}
```

**System dependency:** pydub requires `ffmpeg` for non-WAV formats.
```bash
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Ubuntu/Debian
```

## Required .env values

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | **yes** | Scoring will fail without it |
| `WEBHOOK_SECRET` | yes | Must match Moja's outgoing secret header |
| `TELEGRAM_BOT_TOKEN` | no | Leave blank to disable Telegram alerts |
| `TELEGRAM_CHAT_ID` | no | Your chat or group ID |
| `DATABASE_URL` | no | Defaults to `sqlite:///./calls.db` |
| `WHISPER_MODEL` | no | `base` is a good default; `small` is more accurate |
| `CALLER_CHANNEL` | no | `0`=left channel is caller, `1`=right (confirm in Phase 2) |

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness check |
| `GET` | `/upload` | HTML upload form |
| `POST` | `/upload` | Upload audio file to test the pipeline |
| `POST` | `/webhooks/moja` | Moja AI call-completion webhook |
| `GET` | `/calls` | List scored calls (`?publisher=&buyer=&limit=`) |
| `GET` | `/calls/{call_id}/score` | Full score breakdown |
| `POST` | `/calls/{call_id}/chat` | Ask a question about a specific recording |
| `GET` | `/scorecard` | Aggregate stats by publisher (`?publisher=&buyer=`) |
| `POST` | `/tasks/daily-briefing` | Trigger daily Telegram summary |

## Testing without Moja

**Option A — browser upload:**  Open `http://localhost:8000/upload`, drag in any
stereo MP3/WAV, fill in publisher + buyer, submit.

**Option B — webhook script:**
```bash
python scripts/send_test_webhook.py \
  --recording-url https://example.com/your_call.mp3 \
  --publisher test_pub \
  --buyer default
```

## Per-buyer rubrics

Edit `app/rubrics/buyers.json` to add buyer-specific criteria, weights, and
billable thresholds.  If a buyer key is not found, the `"default"` rubric is
used.

## Project layout

```
app/
  main.py            FastAPI app + DB init
  config.py          Settings (pydantic-settings, reads .env)
  database.py        SQLAlchemy engine + session
  models.py          Call, ChatMessage ORM models
  schemas.py         MojaWebhook pydantic schema
  rubrics/
    buyers.json      Per-buyer scoring rubrics
  routers/
    webhooks.py      POST /webhooks/moja
    upload.py        GET|POST /upload
    calls.py         /calls, /calls/{id}/score, /calls/{id}/chat, /scorecard
    tasks.py         POST /tasks/daily-briefing
  services/
    transcribe.py    Download + faster-whisper stereo transcription
    score.py         Claude-based rubric scoring
    notify.py        Telegram alerts
    pipeline.py      Orchestrator (download→transcribe→score→save→notify)
scripts/
  send_test_webhook.py  POST a sample payload to /webhooks/moja
```
