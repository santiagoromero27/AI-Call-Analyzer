"""
Core pipeline: download → transcribe → score → save → notify.

Two entry points:
  process_call_background()  — single call, used by webhook + single-file upload
  process_batch()            — CSV batch, runs 4 calls in parallel via ThreadPoolExecutor
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..database import SessionLocal
from .. import models
from . import transcribe as svc_transcribe
from . import score as svc_score
from . import notify as svc_notify


def process_call(
    call_id: str,
    recording_url: str,
    publisher: str,
    buyer: str,
    db,
    duration: int | None = None,
    local_audio_path: str | None = None,
    extra: dict | None = None,
) -> models.Call:
    existing = db.query(models.Call).filter(models.Call.call_id == call_id).first()
    if existing:
        if existing.status == "done":
            return existing
        # Failed or stuck — reset so it gets re-processed
        existing.status = "pending"
        existing.score_json = None
        existing.transcript = None
        existing.total_score = None
        existing.billable = None
        existing.conversion_barrier = None
        db.commit()
        call = existing
    else:
        call = None

    extra = extra or {}
    if call is None:
        call = models.Call(
            call_id=call_id,
            publisher=publisher,
            buyer=buyer,
            recording_url=recording_url,
            duration_seconds=duration,
            caller_id=extra.get("caller_id"),
            campaign_name=extra.get("campaign_name"),
            termination_reason=extra.get("termination_reason"),
            batch_id=extra.get("batch_id"),
            status="pending",
        )
        db.add(call)
        db.commit()
        db.refresh(call)

    downloaded_path: str | None = None
    try:
        if local_audio_path:
            segments = svc_transcribe.transcribe(local_audio_path)
        else:
            downloaded_path, segments = svc_transcribe.download_and_transcribe(recording_url)

        termination_reason = extra.get("termination_reason", "")
        no_payout_reason = extra.get("no_payout_reason", "")
        score_result = svc_score.score_call(segments, buyer, termination_reason, no_payout_reason)

        call.transcript = json.dumps(segments)
        call.score_json = json.dumps(score_result)
        call.total_score = score_result["total_score"]
        call.conversion_barrier = score_result.get("conversion_barrier", "")
        call.status = "done"
        db.commit()

        # Only send Telegram for single-call (webhook/upload) flows, not batch
        if not extra.get("batch_id"):
            alert = svc_notify.format_call_alert(call_id, publisher, buyer, score_result)
            svc_notify.send_telegram(alert)

    except Exception as exc:
        call.score_json = json.dumps({"error": str(exc)})
        call.status = "failed"
        db.commit()
        raise

    finally:
        if downloaded_path and os.path.exists(downloaded_path):
            os.unlink(downloaded_path)
        if local_audio_path and os.path.exists(local_audio_path):
            os.unlink(local_audio_path)

    return call


def process_call_background(
    call_id: str,
    recording_url: str,
    publisher: str,
    buyer: str,
    duration: int | None = None,
    local_audio_path: str | None = None,
    extra: dict | None = None,
) -> None:
    db = SessionLocal()
    try:
        process_call(call_id, recording_url, publisher, buyer, db, duration, local_audio_path, extra)
    finally:
        db.close()


# ── Batch processing ─────────────────────────────────────────────────────────

def _bump_batch(batch_id: int, success: bool) -> None:
    db = SessionLocal()
    try:
        batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
        if not batch:
            return
        if success:
            batch.completed += 1
        else:
            batch.failed += 1
        db.commit()
    finally:
        db.close()



def _process_one_row(row: dict, batch_id: int) -> bool:
    import hashlib
    db = SessionLocal()
    try:
        # Prefer Moja's real UUID call_id; fall back to hash of recording_url
        call_id = row.get("call_id") or hashlib.sha1(row["recording_url"].encode()).hexdigest()[:20]
        buyer = (row.get("buyer") or "default").strip().lower().replace(" ", "_")
        publisher = (row.get("publisher") or "unknown").strip()

        raw_duration = row.get("total_call_length", "")
        duration = int(raw_duration) if raw_duration.isdigit() else None

        process_call(
            call_id=call_id,
            recording_url=row["recording_url"],
            publisher=publisher,
            buyer=buyer,
            db=db,
            duration=duration,
            extra={
                "caller_id": row.get("caller_id", ""),
                "campaign_name": row.get("campaign_name", ""),
                "termination_reason": row.get("termination_reason", ""),
                "no_payout_reason": row.get("no_payout_reason", ""),
                "batch_id": batch_id,
            },
        )
        return True
    except Exception:
        return False
    finally:
        db.close()


def process_batch(batch_id: int, rows: list[dict]) -> None:
    """Download, transcribe, and score all rows using 4 parallel workers."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_process_one_row, row, batch_id): row for row in rows}
        for future in as_completed(futures):
            try:
                success = future.result()
            except Exception:
                success = False
            _bump_batch(batch_id, success)
