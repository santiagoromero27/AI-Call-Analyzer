"""Batch management: progress tracking, call list, and cross-call analysis chat."""
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

router = APIRouter()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── Shared HTML chrome ────────────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f8fafc;color:#1e293b}
nav{background:#1e40af;padding:.75rem 1.5rem;display:flex;gap:1.5rem;align-items:center}
nav a{color:#fff;text-decoration:none;font-size:.9rem}nav a:hover{text-decoration:underline}
.brand{font-weight:700;color:#fff}
.container{max-width:1100px;margin:0 auto;padding:1.5rem 1rem}
h1{font-size:1.4rem;margin:0 0 1.2rem}h2{font-size:1.1rem;margin:1.4rem 0 .7rem}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}
th{background:#f1f5f9;padding:.55rem .85rem;text-align:left;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:#475569}
td{padding:.55rem .85rem;border-top:1px solid #e2e8f0;font-size:.85rem;vertical-align:top}
tr:hover td{background:#f8fafc}
.badge{display:inline-block;padding:.15rem .5rem;border-radius:9999px;font-size:.73rem;font-weight:600}
.green{background:#dcfce7;color:#166534}.red{background:#fee2e2;color:#991b1b}
.yellow{background:#fef9c3;color:#854d0e}.blue{background:#dbeafe;color:#1e40af}
.gray{background:#f1f5f9;color:#475569}
.progress{background:#e2e8f0;border-radius:9999px;height:8px;overflow:hidden;margin-top:.3rem}
.progress-bar{height:100%;background:#2563eb;border-radius:9999px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1rem;margin-bottom:1.5rem}
.stat{background:#fff;border-radius:8px;padding:.9rem 1rem;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.stat-label{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
.stat-value{font-size:1.6rem;font-weight:700;margin-top:.2rem}
.btn{display:inline-block;padding:.45rem 1rem;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.85rem;text-decoration:none}
.btn:hover{background:#1d4ed8}.btn-ghost{background:transparent;color:#2563eb;border:1px solid #2563eb}
.btn-ghost:hover{background:#eff6ff}
a{color:#2563eb}
/* chat */
#chat-wrap{display:flex;flex-direction:column;height:520px;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1);overflow:hidden}
#messages{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.75rem}
.msg{padding:.6rem .9rem;border-radius:8px;max-width:80%;line-height:1.5;font-size:.875rem;white-space:pre-wrap}
.msg.user{background:#2563eb;color:#fff;align-self:flex-end}
.msg.assistant{background:#f1f5f9;align-self:flex-start}
#chat-form{display:flex;gap:.5rem;padding:.75rem;border-top:1px solid #e2e8f0}
#chat-input{flex:1;padding:.5rem .75rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem}
#send-btn{padding:.5rem 1rem;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.875rem}
#send-btn:disabled{opacity:.5;cursor:not-allowed}
.barrier{font-size:.8rem;color:#6b7280;max-width:340px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
"""


def _nav() -> str:
    return """<nav><span class="brand">Call Analyzer</span>
<a href="/batches">Batches</a><a href="/scorecard">Scorecard</a>
<a href="/upload">Single Upload</a><a href="/upload/csv">CSV Upload</a></nav>"""


def _wrap(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><title>{title} — Call Analyzer</title>
<style>{_CSS}</style></head><body>{_nav()}
<div class="container">{body}</div></body></html>"""


def _score_badge(score: float | None) -> str:
    if score is None:
        return '<span class="badge gray">pending</span>'
    colour = "green" if score >= 70 else ("yellow" if score >= 50 else "red")
    return f'<span class="badge {colour}">{score:.0f}/100</span>'


def _billable_badge(billable: bool | None) -> str:
    if billable is None:
        return ""
    return f'<span class="badge {"green" if billable else "red"}">{"billable" if billable else "not billable"}</span>'


# ── API endpoints ─────────────────────────────────────────────────────────────

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
        "billable_count": sum(1 for c in calls if c.billable),
        "calls": [
            {
                "call_id": c.call_id,
                "caller_id": c.caller_id,
                "publisher": c.publisher,
                "buyer": c.buyer,
                "campaign_name": c.campaign_name,
                "termination_reason": c.termination_reason,
                "total_score": c.total_score,
                "billable": c.billable,
                "conversion_barrier": c.conversion_barrier,
                "status": c.status,
            }
            for c in calls
        ],
    }


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
        raise HTTPException(400, "No scored calls in this batch yet")

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
                "and answer questions about why calls did not close.\n\n" + context
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
        lines.append("")

    return "\n".join(lines)


# ── HTML pages ────────────────────────────────────────────────────────────────

@router.get("/batches", response_class=HTMLResponse)
def batches_list(db: Session = Depends(get_db)):
    batches = db.query(models.Batch).order_by(models.Batch.created_at.desc()).all()

    if not batches:
        body = """<h1>Batches</h1>
<p>No batches yet. <a href="/upload/csv">Upload a CSV</a> to get started.</p>"""
        return _wrap("Batches", body)

    rows = ""
    for b in batches:
        done = b.completed + b.failed
        pct = int(done / b.total * 100) if b.total else 0
        progress = f"""<div style="font-size:.8rem;color:#64748b">{done}/{b.total}</div>
<div class="progress"><div class="progress-bar" style="width:{pct}%"></div></div>"""
        rows += f"""<tr>
<td><a href="/batches/{b.id}">{b.name or f'Batch #{b.id}'}</a></td>
<td>{progress}</td>
<td>{b.completed}</td>
<td>{b.failed}</td>
<td>{b.created_at.strftime('%b %d %H:%M')}</td>
<td><a class="btn btn-ghost" href="/batches/{b.id}/analyze">Analyze</a></td>
</tr>"""

    body = f"""<h1>Batches</h1>
<a class="btn" href="/upload/csv" style="float:right;margin-top:-.5rem">+ New CSV upload</a>
<table>
<thead><tr><th>Name</th><th>Progress</th><th>Done</th><th>Failed</th><th>Created</th><th></th></tr></thead>
<tbody>{rows}</tbody>
</table>"""
    return _wrap("Batches", body)


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
    billable = sum(1 for c in calls if c.billable)

    # Auto-refresh if still processing
    refresh = '<meta http-equiv="refresh" content="8">' if done < batch.total else ""

    stats = f"""<div class="stat-grid">
<div class="stat"><div class="stat-label">Total</div><div class="stat-value">{batch.total}</div></div>
<div class="stat"><div class="stat-label">Processed</div><div class="stat-value">{done}</div></div>
<div class="stat"><div class="stat-label">Billable</div><div class="stat-value">{billable}</div></div>
<div class="stat"><div class="stat-label">Avg score</div><div class="stat-value">{avg}</div></div>
</div>
<div class="progress" style="margin-bottom:1.5rem">
  <div class="progress-bar" style="width:{pct}%"></div>
</div>"""

    rows = ""
    for c in calls:
        barrier_cell = f'<div class="barrier" title="{(c.conversion_barrier or "").replace(chr(34), chr(39))}">{c.conversion_barrier or "—"}</div>'
        rows += f"""<tr>
<td>{c.caller_id or "—"}</td>
<td>{c.publisher}</td>
<td>{c.buyer}</td>
<td>{c.termination_reason or "—"}</td>
<td>{_score_badge(c.total_score)}</td>
<td>{_billable_badge(c.billable)}</td>
<td>{barrier_cell}</td>
<td><a href="/calls/{c.call_id}">View</a></td>
</tr>"""

    body = f"""{refresh}
<h1>{batch.name or f'Batch #{batch.id}'}</h1>
<a class="btn" href="/batches/{batch_id}/analyze" style="float:right;margin-top:-.5rem">Analyze with AI</a>
{stats}
<table>
<thead><tr>
<th>Caller</th><th>Publisher</th><th>Buyer</th><th>Termination</th>
<th>Score</th><th>Billable</th><th>Why it didn't close</th><th></th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""
    return _wrap(batch.name or f"Batch #{batch_id}", body)


@router.get("/batches/{batch_id}/analyze", response_class=HTMLResponse)
def batch_analyze(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    history = (
        db.query(models.BatchMessage)
        .filter(models.BatchMessage.batch_id == batch_id)
        .order_by(models.BatchMessage.created_at)
        .all()
    )

    msg_html = ""
    for m in history:
        msg_html += f'<div class="msg {m.role}">{m.content}</div>'

    scored_count = (
        db.query(models.Call)
        .filter(models.Call.batch_id == batch_id, models.Call.total_score.isnot(None))
        .count()
    )

    body = f"""<h1>{batch.name or f'Batch #{batch_id}'} — AI Analysis</h1>
<p style="font-size:.875rem;color:#64748b;margin-bottom:1rem">
  {scored_count} scored calls · <a href="/batches/{batch_id}">← Back to batch</a>
</p>
<div id="chat-wrap">
  <div id="messages">{msg_html or '<div class="msg assistant">Ask me anything about these calls — e.g. "What are the top 3 reasons deals didn\'t close?" or "Which publisher sends the best callers?"</div>'}</div>
  <form id="chat-form">
    <input id="chat-input" type="text" placeholder="Ask about this batch…" autocomplete="off" autofocus>
    <button id="send-btn" type="submit">Send</button>
  </form>
</div>
<script>
const form = document.getElementById('chat-form');
const input = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
const msgs = document.getElementById('messages');
const batchId = {batch_id};

function addMsg(role, text) {{
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
}}

form.addEventListener('submit', async e => {{
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMsg('user', text);
  input.value = '';
  btn.disabled = true;
  btn.textContent = '…';
  try {{
    const res = await fetch('/batches/' + batchId + '/chat', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{message: text}})
    }});
    const data = await res.json();
    addMsg('assistant', data.reply || data.detail || 'Error');
  }} catch(err) {{
    addMsg('assistant', 'Request failed: ' + err.message);
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Send';
    input.focus();
  }}
}});
msgs.scrollTop = msgs.scrollHeight;
</script>"""
    return _wrap(f"Analyze — {batch.name}", body)
