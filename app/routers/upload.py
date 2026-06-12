"""Upload routes: paste a single URL or upload a CSV batch."""
import csv
import hashlib
import io
from threading import Thread

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from ..database import SessionLocal
from .. import models
from ..services.pipeline import process_call_background, process_batch
from .shared_ui import page

router = APIRouter()

_FORM_BODY = """
<h1>Upload Calls</h1>
<div class="tab-section">
<div class="tabs">
  <button class="tab active" data-target="url-tab">Single URL</button>
  <button class="tab" data-target="csv-tab">CSV Batch</button>
</div>

<div id="url-tab" class="tab-pane active">
  <p style="font-size:.875rem;color:#64748b;margin-top:0">
    Paste an S3 recording URL directly and run it through the pipeline.
  </p>
  <form method="post" action="/upload/url">
    <label class="field">Recording URL (S3 / presigned)
      <input type="url" name="recording_url" placeholder="https://s3.amazonaws.com/…" required>
    </label>
    <label class="field">Caller ID
      <input type="text" name="caller_id" placeholder="+15551234567">
    </label>
    <label class="field">Publisher
      <input type="text" name="publisher" placeholder="e.g. Flex Marketing" required>
    </label>
    <label class="field">Buyer
      <input type="text" name="buyer" placeholder="e.g. TrueChoice" required>
    </label>
    <label class="field">Campaign
      <input type="text" name="campaign_name" placeholder="e.g. FE Inbounds">
    </label>
    <label class="field">Termination reason
      <input type="text" name="termination_reason" placeholder="e.g. Caller hung up">
    </label>
    <button class="btn" type="submit" style="margin-top:1.2rem">Process call</button>
  </form>
</div>

<div id="csv-tab" class="tab-pane">
  <p style="font-size:.875rem;color:#64748b;margin-top:0">
    Upload a Moja export CSV. Required column: <code>Recording URL</code>.<br>
    Recognised columns: <code>Call ID, Caller ID, Publisher, Buyer, Campaign,
    Total Call Length, Termination Reason, No Payout Reason</code>.
  </p>
  <form method="post" action="/upload/csv" enctype="multipart/form-data">
    <label class="field">CSV file
      <input type="file" name="file" accept=".csv,text/csv" required>
    </label>
    <label class="field">Batch name (optional)
      <input type="text" name="batch_name" placeholder="e.g. June 11 leads">
    </label>
    <button class="btn" type="submit" style="margin-top:1.2rem">Start batch</button>
  </form>
</div>
</div>
"""


@router.get("/upload", response_class=HTMLResponse)
async def upload_form():
    return page("Upload", _FORM_BODY)


# ── Single URL ────────────────────────────────────────────────────────────────

@router.post("/upload/url")
async def upload_url(
    background_tasks: BackgroundTasks,
    recording_url: str = Form(...),
    publisher: str = Form(...),
    buyer: str = Form(...),
    caller_id: str = Form(default=""),
    campaign_name: str = Form(default=""),
    termination_reason: str = Form(default=""),
):
    call_id = hashlib.sha1(recording_url.encode()).hexdigest()[:20]
    buyer_key = buyer.strip().lower().replace(" ", "_")

    background_tasks.add_task(
        process_call_background,
        call_id=call_id,
        recording_url=recording_url,
        publisher=publisher.strip(),
        buyer=buyer_key,
        extra={
            "caller_id": caller_id.strip(),
            "campaign_name": campaign_name.strip(),
            "termination_reason": termination_reason.strip(),
        },
    )
    return RedirectResponse(f"/calls/{call_id}", status_code=303)


# ── CSV batch ─────────────────────────────────────────────────────────────────

_REQUIRED_COL = "recording_url"
_KNOWN_COLS = {
    "recording_url", "caller_id", "buyer", "publisher",
    "campaign_name", "campaign",
    "call_id",
    "termination_reason",
    "total_call_length",
    "no_payout_reason",
}


def _norm(h: str) -> str:
    return h.strip().lower().replace(" ", "_")


@router.get("/upload/csv", response_class=HTMLResponse)
async def csv_form():
    return page("Upload", _FORM_BODY)


@router.post("/upload/csv")
async def upload_csv(
    file: UploadFile = File(...),
    batch_name: str = Form(default=""),
):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return HTMLResponse(page("Error", "<h1>Error</h1><p>CSV has no headers.</p>"), status_code=400)

    header_map = {_norm(h): h for h in reader.fieldnames}
    if _REQUIRED_COL not in header_map:
        return HTMLResponse(
            page("Error", f"<h1>Error</h1><p>CSV must have a <code>recording_url</code> / <code>Recording URL</code> column.</p>"),
            status_code=400,
        )

    rows = []
    for raw_row in reader:
        row = {k: raw_row[v].strip() for k, v in header_map.items() if k in _KNOWN_COLS}
        if "campaign" in row and "campaign_name" not in row:
            row["campaign_name"] = row.pop("campaign")
        if row.get("recording_url"):
            rows.append(row)

    if not rows:
        return HTMLResponse(page("Error", "<h1>Error</h1><p>No rows with a recording_url found.</p>"), status_code=400)

    db = SessionLocal()
    try:
        batch = models.Batch(
            name=batch_name.strip() or file.filename or "CSV batch",
            total=len(rows),
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        batch_id = batch.id
    finally:
        db.close()

    Thread(target=process_batch, args=(batch_id, rows), daemon=True).start()
    return RedirectResponse("/", status_code=303)
