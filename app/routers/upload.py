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
<div class="upload-wrap">
  <div class="tab-section">
    <div class="tabs">
      <button class="tab-btn active" data-target="url-tab">Single URL</button>
      <button class="tab-btn" data-target="csv-tab">CSV Batch</button>
    </div>

    <div id="url-tab" class="tab-pane active">
      <div class="dropzone" style="padding:28px 24px;text-align:left">
        <form method="post" action="/upload/url">
          <label class="field-label">Recording URL (S3 / presigned)
            <input type="url" name="recording_url" placeholder="https://s3.amazonaws.com/…" required>
          </label>
          <label class="field-label">Caller ID
            <input type="text" name="caller_id" placeholder="+15551234567">
          </label>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <label class="field-label">Publisher
              <input type="text" name="publisher" placeholder="Flex Marketing" required>
            </label>
            <label class="field-label">Buyer
              <input type="text" name="buyer" placeholder="TrueChoice" required>
            </label>
          </div>
          <label class="field-label">Campaign
            <input type="text" name="campaign_name" placeholder="FE Inbounds">
          </label>
          <label class="field-label">Termination reason
            <input type="text" name="termination_reason" placeholder="Caller hung up">
          </label>
          <button type="submit" class="btn btn-primary" style="margin-top:18px">Process call →</button>
        </form>
      </div>
    </div>

    <div id="csv-tab" class="tab-pane">
      <div class="dropzone" style="padding:28px 24px;text-align:left">
        <form method="post" action="/upload/csv" enctype="multipart/form-data">
          <label class="field-label">Group name
            <input type="text" name="batch_name" placeholder="e.g. June Week 1, TrueChoice Inbounds">
          </label>
          <div style="margin-top:16px">
            <input type="file" name="file" accept=".csv,text/csv" id="csv-file" style="display:none"
              onchange="document.getElementById('csv-name').textContent=this.files[0].name;document.getElementById('csv-name').style.display='block';document.getElementById('csv-submit').style.display='inline-flex'">
            <div id="csv-name" style="display:none;font-size:12.5px;color:var(--acc);font-family:var(--mono);margin-bottom:10px;word-break:break-all"></div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
              <button type="button" class="btn btn-sm" onclick="document.getElementById('csv-file').click()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z"/><path d="M14 3v5h5"/></svg>
                Choose CSV file
              </button>
              <button type="submit" id="csv-submit" class="btn btn-primary btn-sm" style="display:none">
                Process batch →
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>"""


@router.get("/upload", response_class=HTMLResponse)
async def upload_form():
    return page("Upload", _FORM_BODY, active_nav="upload")


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
    return page("Upload", _FORM_BODY, active_nav="upload")


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
    return RedirectResponse(f"/batches/{batch_id}", status_code=303)
