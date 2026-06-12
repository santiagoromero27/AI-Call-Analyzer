import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from ..config import settings
from ..schemas import MojaWebhook
from ..services.pipeline import process_call_background

router = APIRouter()


def _verify_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
    if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


@router.post("/webhooks/moja")
async def moja_webhook(
    payload: MojaWebhook,
    background_tasks: BackgroundTasks,
    _: None = Depends(_verify_secret),
):
    # Moja has no call-ID tag, so derive a stable unique ID from the recording URL.
    # SHA-1 of the URL is collision-resistant enough for < 50 calls/day and makes
    # the handler idempotent if Moja retries the same event.
    call_id = hashlib.sha1(payload.recording_url.encode()).hexdigest()[:20]

    # Normalize buyer_name for rubric key lookup (e.g. "My Buyer" → "my_buyer")
    buyer = payload.buyer_name.strip().lower().replace(" ", "_")
    publisher = payload.publisher_name.strip()

    background_tasks.add_task(
        process_call_background,
        call_id=call_id,
        recording_url=payload.recording_url,
        publisher=publisher,
        buyer=buyer,
        extra={
            "caller_id": payload.caller_id,
            "campaign_name": payload.campaign_name,
        },
    )
    return {"status": "queued", "call_id": call_id}
