"""Batch management: group list, detail view, and dedicated AI chat screen."""
import json

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..schemas import ChatRequest
from ..services.model_settings import get_model
from .shared_ui import page, score_pill

router = APIRouter()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── JSON API ──────────────────────────────────────────────────────────────────

@router.get("/api/batches")
def api_list_batches(db: Session = Depends(get_db)):
    batches = db.query(models.Batch).order_by(models.Batch.created_at.desc()).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "total": b.total,
            "completed": b.completed,
            "failed": b.failed,
            "created_at": b.created_at.isoformat(),
        }
        for b in batches
    ]


@router.get("/api/batches/{batch_id}")
def api_batch_detail(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")
    calls = (
        db.query(models.Call)
        .filter(models.Call.batch_id == batch_id)
        .order_by(models.Call.created_at)
        .all()
    )
    scored = [c for c in calls if c.total_score is not None]
    avg_score = round(sum(c.total_score for c in scored) / len(scored), 1) if scored else None
    return {
        "id": batch.id,
        "name": batch.name,
        "total": batch.total,
        "completed": batch.completed,
        "failed": batch.failed,
        "avg_score": avg_score,
        "calls": [
            {
                "call_id": c.call_id,
                "caller_id": c.caller_id,
                "publisher": c.publisher,
                "buyer": c.buyer,
                "campaign_name": c.campaign_name,
                "termination_reason": c.termination_reason,
                "total_score": c.total_score,
                "conversion_barrier": c.conversion_barrier,
                "status": c.status,
            }
            for c in calls
        ],
    }


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/batches/{batch_id}/chat")
def batch_chat(batch_id: int, req: ChatRequest, db: Session = Depends(get_db)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    calls = (
        db.query(models.Call)
        .filter(models.Call.batch_id == batch_id, models.Call.total_score.isnot(None))
        .all()
    )
    if not calls:
        return {"reply": "No scored calls in this batch yet — check back once processing completes."}

    context = _build_batch_context(batch, calls)

    history = (
        db.query(models.BatchMessage)
        .filter(models.BatchMessage.batch_id == batch_id)
        .order_by(models.BatchMessage.created_at)
        .all()
    )

    messages = [
        {
            "role": "user",
            "content": (
                "You are a sales analytics assistant. Analyse the following batch of call data "
                "and answer questions about caller behavior and why calls did not close.\n\n"
                + context
            ),
        },
        {
            "role": "assistant",
            "content": "Got it — I've reviewed all the calls. What would you like to know?",
        },
    ]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": req.message})

    response = _get_client().messages.create(
        model=get_model(),
        max_tokens=1200,
        messages=messages,
    )
    reply = response.content[0].text.strip()

    db.add(models.BatchMessage(batch_id=batch_id, role="user", content=req.message))
    db.add(models.BatchMessage(batch_id=batch_id, role="assistant", content=reply))
    db.commit()

    return {"reply": reply}


def _build_batch_context(batch: models.Batch, calls: list) -> str:
    scored = [c for c in calls if c.total_score is not None]
    avg = round(sum(c.total_score for c in scored) / len(scored), 1) if scored else 0

    lines = [
        f"BATCH: {batch.name or f'Batch #{batch.id}'}",
        f"Calls: {len(calls)} | Scored: {len(scored)} | Avg score: {avg}/100",
        "",
        "CALL-BY-CALL BREAKDOWN:",
    ]
    for i, c in enumerate(calls, 1):
        score_str = f"{c.total_score:.0f}/100" if c.total_score else "not scored"
        lines.append(
            f"{i}. {c.caller_id or c.call_id} | {c.publisher} → {c.buyer}"
            f" | Score: {score_str}"
        )
        if c.termination_reason:
            lines.append(f"   Termination: {c.termination_reason}")
        if c.conversion_barrier:
            lines.append(f"   Why it didn't close: {c.conversion_barrier}")
        if c.transcript:
            try:
                segments = json.loads(c.transcript)
                transcript_lines = "\n".join(
                    f"   [{s['start']:.1f}s] {s['speaker'].upper()}: {s['text']}"
                    for s in segments
                )
                lines.append(f"   TRANSCRIPT:\n{transcript_lines}")
            except Exception:
                pass
        lines.append("")

    return "\n".join(lines)


# ── HTML pages ────────────────────────────────────────────────────────────────

@router.get("/batches", response_class=HTMLResponse)
def batches_list(db: Session = Depends(get_db)):
    batches = db.query(models.Batch).order_by(models.Batch.created_at.desc()).all()
    total_calls = sum(b.total for b in batches)

    topbar_extra = '<a href="/upload" class="btn btn-sm btn-primary">+ Upload CSV</a>'

    if not batches:
        body = """<div class="content-pad">
  <div style="text-align:center;padding:60px 0">
    <div style="font-size:15px;font-weight:600;margin-bottom:8px">No groups yet</div>
    <div style="font-size:13px;color:var(--text-3);margin-bottom:20px">Upload a CSV to create your first group of calls</div>
    <a href="/upload" class="btn btn-primary">Upload CSV →</a>
  </div>
</div>"""
        return page("Batches", body, active_nav="batches", topbar_extra=topbar_extra)

    stats = f"""<div class="stat-row">
  <div class="stat-card">
    <div class="sc-label">Total groups</div>
    <div class="sc-value">{len(batches)}</div>
    <div class="sc-sub">CSV uploads</div>
  </div>
  <div class="stat-card">
    <div class="sc-label">Total calls</div>
    <div class="sc-value">{total_calls}</div>
    <div class="sc-sub">across all groups</div>
  </div>
</div>"""

    rows = ""
    for b in batches:
        done = b.completed + b.failed
        pct = int(done / b.total * 100) if b.total else 0
        progress = f"""<div style="display:flex;align-items:center;gap:8px">
  <span class="mono" style="font-size:12px;color:var(--text-3);white-space:nowrap">{done}/{b.total}</span>
  <div style="flex:1;min-width:80px;background:var(--border-2);border-radius:999px;height:5px;overflow:hidden">
    <div style="height:100%;background:var(--acc);border-radius:999px;width:{pct}%"></div>
  </div>
</div>"""
        rows += f"""<tr onclick="location.href='/batches/{b.id}'" style="cursor:pointer">
  <td style="font-weight:500">{b.name or f"Batch #{b.id}"}</td>
  <td class="mono">{b.total}</td>
  <td style="min-width:160px">{progress}</td>
  <td class="mono cell-muted" style="white-space:nowrap">{b.created_at.strftime('%Y-%m-%d %H:%M')}</td>
</tr>"""

    body = f"""<div class="content-pad">
{stats}
<div class="table-wrap">
  <div style="overflow-x:auto">
    <table class="calls">
      <thead><tr>
        <th>Group name</th><th>Calls</th><th>Progress</th><th>Created</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
</div>"""

    return page("Batches", body, active_nav="batches", topbar_extra=topbar_extra)


@router.get("/batches/{batch_id}", response_class=HTMLResponse)
def batch_detail(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    calls = (
        db.query(models.Call)
        .filter(models.Call.batch_id == batch_id)
        .order_by(models.Call.created_at)
        .all()
    )

    done = batch.completed + batch.failed
    pct = int(done / batch.total * 100) if batch.total else 0
    scored = [c for c in calls if c.total_score is not None]
    avg = round(sum(c.total_score for c in scored) / len(scored), 1) if scored else 0
    processing = done < batch.total

    def mc(k, v):
        return f'<div class="meta-cell"><div class="k">{k}</div><div class="v" style="font-family:var(--mono);font-size:13px">{v}</div></div>'

    meta_html = f"""<div class="meta-grid">
  {mc("Total calls", str(batch.total))}
  {mc("Processed", str(done))}
  {mc("Avg score", f"{avg}/100" if scored else "—")}
  {mc("Failed", str(batch.failed))}
</div>"""

    progress_html = f"""<div style="background:var(--border-2);border-radius:999px;height:5px;overflow:hidden;margin:0 0 8px">
  <div style="height:100%;background:var(--acc);border-radius:999px;width:{pct}%"></div>
</div>
<div style="font-size:12px;color:var(--text-3);margin-bottom:20px">Processing {done}/{batch.total} calls…</div>""" if processing else ""

    spark_ico = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/></svg>'

    rows = ""
    for c in calls:
        sp = score_pill(c.total_score)
        status_html = '<span class="pill tone-amber">pending</span>' if c.status == "pending" else \
                      '<span class="pill tone-red">failed</span>' if c.status == "failed" else ""
        rows += f"""<tr onclick="location.href='/calls/{c.call_id}'" style="cursor:pointer">
  <td class="mono">{c.caller_id or "—"}</td>
  <td class="cell-muted">{c.publisher}</td>
  <td class="cell-muted">{c.buyer}</td>
  <td class="cell-muted" style="font-size:12px">{c.termination_reason or "—"}</td>
  <td>{sp}{" " + status_html if status_html else ""}</td>
</tr>"""

    table_html = f"""<div class="table-wrap">
  <div style="overflow-x:auto">
    <table class="calls">
      <thead><tr>
        <th>Caller ID</th><th>Publisher</th><th>Buyer</th><th>Termination</th><th>Score</th>
      </tr></thead>
      <tbody>{rows or '<tr><td colspan="5" style="text-align:center;color:var(--text-3);padding:32px">No calls yet — processing in background</td></tr>'}</tbody>
    </table>
  </div>
</div>"""

    body = f"""<div class="content-pad">
<div class="detail-title">{batch.name or f"Batch #{batch_id}"}</div>
{meta_html}
{progress_html}
<div class="section-title">{spark_ico} Calls</div>
{table_html}
</div>"""

    breadcrumb = (
        f'<span class="crumb" onclick="location.href=\'/batches\'" style="cursor:pointer">Batches</span>'
        f'<span class="crumb-sep"> / </span>'
        f'<span>{batch.name or f"Batch #{batch_id}"}</span>'
    )

    ask_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M21 11.5a8.4 8.4 0 01-9 8.4L4 21l1.1-3.5A8.5 8.5 0 1121 11.5z"/><circle cx="8.5" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="11.5" r="1" fill="currentColor" stroke="none"/></svg>'
    topbar_extra = f'<a href="/batches/{batch_id}/analyze" class="btn btn-sm btn-primary">{ask_ico} Ask AI</a>'

    auto_refresh = "<script>setTimeout(() => location.reload(), 8000);</script>" if processing else ""

    return page(
        f"Batch — {batch.name or batch_id}", body,
        active_nav="batches",
        breadcrumb=breadcrumb,
        topbar_extra=topbar_extra,
        extra_js=auto_refresh,
    )


@router.get("/batches/{batch_id}/analyze", response_class=HTMLResponse)
def batch_analyze(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    scored_count = (
        db.query(models.Call)
        .filter(models.Call.batch_id == batch_id, models.Call.total_score.isnot(None))
        .count()
    )

    history = (
        db.query(models.BatchMessage)
        .filter(models.BatchMessage.batch_id == batch_id)
        .order_by(models.BatchMessage.created_at)
        .all()
    )

    send_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M5 12l15-7-7 15-2-6-6-2z"/></svg>'
    spark_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/></svg>'

    SUGGESTIONS = [
        "Why didn't most callers apply?",
        "Which publisher sends the best callers?",
        "What % of calls reached the application step?",
        "How do agents handle price objections?",
    ]
    suggests_html = "".join(
        f'<button class="suggest-btn" onclick="sendMsg(this.querySelector(\'span\').textContent)">'
        f'{spark_ico}<span>{s}</span></button>'
        for s in SUGGESTIONS
    )

    msgs_html = ""
    if not history:
        msgs_html = (
            f'<div class="msg-ai"><div class="msg-av">AI</div>'
            f'<div class="bubble-ai">Ask me anything about calls in this group. Try a suggestion below.</div></div>'
            f'<div class="suggest-list">{suggests_html}</div>'
        )
    else:
        for m in history:
            if m.role == "user":
                msgs_html += f'<div class="msg-user"><div class="bubble-user">{m.content}</div></div>'
            else:
                msgs_html += f'<div class="msg-ai"><div class="msg-av">AI</div><div class="bubble-ai">{m.content}</div></div>'

    body = f"""<div style="display:flex;justify-content:center;height:100%">
<div class="ask-wrap">
  <div class="range-bar">
    <span style="font-size:13px;font-weight:600;color:var(--text)">{batch.name or f"Batch #{batch_id}"}</span>
    <span class="call-count-badge">{scored_count} scored calls</span>
  </div>
  <div class="chat-scroll" id="chat-scroll">{msgs_html}</div>
  <div class="chat-foot">
    <div class="composer" id="composer">
      <textarea id="chat-input" rows="1" placeholder="Ask about this group…"></textarea>
      <button class="send-btn" id="send-btn" disabled>{send_ico}</button>
    </div>
  </div>
</div>
</div>"""

    breadcrumb = (
        f'<span class="crumb" onclick="location.href=\'/batches\'" style="cursor:pointer">Batches</span>'
        f'<span class="crumb-sep"> / </span>'
        f'<span class="crumb" onclick="location.href=\'/batches/{batch_id}\'" style="cursor:pointer">'
        f'{batch.name or f"Batch #{batch_id}"}</span>'
        f'<span class="crumb-sep"> / </span>'
        f'<span>Ask AI</span>'
    )

    js = f"""<script>
const inp = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
const scroll = document.getElementById('chat-scroll');
inp.addEventListener('input', () => {{
  inp.style.height = 'auto'; inp.style.height = inp.scrollHeight + 'px';
  btn.disabled = !inp.value.trim();
}});
inp.addEventListener('keydown', e => {{ if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); if (!btn.disabled) send(); }} }});
btn.addEventListener('click', send);
function sendMsg(text) {{ inp.value = text; btn.disabled = false; send(); }}
function addBubble(role, text) {{
  const d = document.createElement('div');
  d.className = role === 'user' ? 'msg-user' : 'msg-ai';
  d.innerHTML = role === 'user'
    ? '<div class="bubble-user">' + text + '</div>'
    : '<div class="msg-av">AI</div><div class="bubble-ai">' + text + '</div>';
  scroll.appendChild(d); scroll.scrollTop = scroll.scrollHeight;
}}
function send() {{
  const text = inp.value.trim(); if (!text) return;
  addBubble('user', text);
  inp.value = ''; inp.style.height = 'auto'; btn.disabled = true;
  const dot = document.createElement('div');
  dot.className = 'msg-ai'; dot.id = 'typing';
  dot.innerHTML = '<div class="msg-av">AI</div><div class="typing"><span></span><span></span><span></span></div>';
  scroll.appendChild(dot); scroll.scrollTop = scroll.scrollHeight;
  fetch('/batches/{batch_id}/chat', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{message: text}})
  }}).then(r => r.json()).then(d => {{
    document.getElementById('typing')?.remove();
    addBubble('ai', d.reply || d.detail || 'Error');
  }}).catch(err => {{
    document.getElementById('typing')?.remove();
    addBubble('ai', 'Request failed: ' + err.message);
  }});
}}
scroll.scrollTop = scroll.scrollHeight;
</script>"""

    return page(
        f"Ask — {batch.name or batch_id}", body,
        active_nav="batches", full_bleed=True,
        breadcrumb=breadcrumb, extra_js=js,
    )
