"""Per-call routes: detail page + AI chat API."""
import json

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..schemas import ChatRequest
from .shared_ui import page, badge_score

router = APIRouter()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── JSON API ──────────────────────────────────────────────────────────────────

@router.get("/api/calls")
def api_list_calls(
    publisher: str | None = None,
    buyer: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(models.Call)
    if publisher:
        q = q.filter(models.Call.publisher == publisher)
    if buyer:
        q = q.filter(models.Call.buyer == buyer)
    calls = q.order_by(models.Call.created_at.desc()).limit(limit).all()
    return [
        {
            "call_id": c.call_id,
            "caller_id": c.caller_id,
            "publisher": c.publisher,
            "buyer": c.buyer,
            "total_score": c.total_score,
            "duration_seconds": c.duration_seconds,
            "created_at": c.created_at.isoformat(),
        }
        for c in calls
    ]


@router.post("/calls/{call_id}/chat")
def chat_about_call(call_id: str, req: ChatRequest, db: Session = Depends(get_db)):
    call = db.query(models.Call).filter(models.Call.call_id == call_id).first()
    if not call:
        raise HTTPException(404, "Call not found")
    if not call.transcript:
        raise HTTPException(400, "Transcript not ready yet — check back in a moment")

    segments = json.loads(call.transcript)
    transcript_text = "\n".join(
        f"[{s['start']:.1f}s] {s['speaker'].upper()}: {s['text']}"
        for s in segments
    )

    system_ctx = (
        f"You are a sales analyst reviewing a specific call.\n\n"
        f"CALL METADATA:\n"
        f"Caller: {call.caller_id or 'unknown'}\n"
        f"Publisher: {call.publisher} | Buyer: {call.buyer}\n"
        f"Duration: {call.duration_seconds}s\n"
        f"Score: {call.total_score}/100\n"
        f"Termination: {call.termination_reason or 'unknown'}\n"
        f"Why it didn't close: {call.conversion_barrier or 'not analyzed'}\n\n"
        f"TRANSCRIPT:\n{transcript_text}"
    )

    history = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.call_db_id == call.id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )

    messages = [
        {"role": "user", "content": system_ctx},
        {"role": "assistant", "content": "I've reviewed this call. What would you like to know?"},
    ]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": req.message})

    response = _get_client().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=800,
        messages=messages,
    )
    reply = response.content[0].text.strip()

    db.add(models.ChatMessage(call_db_id=call.id, role="user", content=req.message))
    db.add(models.ChatMessage(call_db_id=call.id, role="assistant", content=reply))
    db.commit()

    return {"reply": reply}


@router.get("/scorecard")
def scorecard(
    publisher: str | None = None,
    buyer: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Call).filter(models.Call.total_score.isnot(None))
    if publisher:
        q = q.filter(models.Call.publisher == publisher)
    if buyer:
        q = q.filter(models.Call.buyer == buyer)
    calls = q.all()
    if not calls:
        return {"count": 0, "message": "No scored calls yet"}
    total = len(calls)
    billable = sum(1 for c in calls if c.billable)
    avg_score = round(sum(c.total_score for c in calls) / total, 1)
    by_publisher: dict = {}
    for c in calls:
        p = c.publisher
        if p not in by_publisher:
            by_publisher[p] = {"count": 0, "billable": 0, "score_sum": 0.0}
        by_publisher[p]["count"] += 1
        by_publisher[p]["score_sum"] += c.total_score
        if c.billable:
            by_publisher[p]["billable"] += 1
    for p, s in by_publisher.items():
        s["avg_score"] = round(s["score_sum"] / s["count"], 1)
        s["billable_rate_pct"] = round(s["billable"] / s["count"] * 100, 1)
        del s["score_sum"]
    return {
        "total_calls": total,
        "billable_calls": billable,
        "billable_rate_pct": round(billable / total * 100, 1),
        "avg_score": avg_score,
        "by_publisher": by_publisher,
    }


# ── Call detail HTML page ─────────────────────────────────────────────────────

@router.post("/calls/{call_id}/delete")
def delete_call(call_id: str, db: Session = Depends(get_db)):
    call = db.query(models.Call).filter(models.Call.call_id == call_id).first()
    if not call:
        raise HTTPException(404, "Call not found")
    db.query(models.ChatMessage).filter(models.ChatMessage.call_db_id == call.id).delete()
    db.delete(call)
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/calls/{call_id}", response_class=HTMLResponse)
def call_detail(call_id: str, db: Session = Depends(get_db)):
    call = db.query(models.Call).filter(models.Call.call_id == call_id).first()
    if not call:
        raise HTTPException(404, "Call not found")

    # Metadata card
    def meta(label: str, value: str) -> str:
        return f'<div class="meta-item"><div class="label">{label}</div><div class="value">{value or "—"}</div></div>'

    duration_str = f"{call.duration_seconds}s" if call.duration_seconds else "—"
    meta_html = f"""<div class="card">
  <div class="meta-grid">
    {meta("Caller ID", call.caller_id)}
    {meta("Publisher", call.publisher)}
    {meta("Buyer", call.buyer)}
    {meta("Campaign", call.campaign_name)}
    {meta("Duration", duration_str)}
    {meta("Termination", call.termination_reason)}
    {meta("No-payout reason", call.no_payout_reason)}
    <div class="meta-item">
      <div class="label">Score</div>
      <div class="value">{badge_score(call.total_score)}</div>
    </div>
    {meta("Date", call.created_at.strftime("%b %d, %Y %H:%M"))}
  </div>
</div>"""

    barrier_html = ""
    if call.conversion_barrier:
        barrier_html = f"""<div style="background:#fef9c3;border-left:4px solid #eab308;
padding:.85rem 1.1rem;border-radius:0 8px 8px 0;margin-bottom:1rem;font-size:.875rem;line-height:1.6">
<span style="font-weight:600;color:#854d0e">Why it didn't close: </span>{call.conversion_barrier}
</div>"""
    elif call.status == "pending":
        barrier_html = '<div class="card" style="color:#94a3b8">Processing… check back in a moment.</div>'

    # Chat history
    history = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.call_db_id == call.id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )
    msg_html = "".join(f'<div class="msg {m.role}">{m.content}</div>' for m in history)
    if not msg_html:
        msg_html = '<div class="msg assistant">Ask me anything about this call — e.g. "At what point did the caller lose interest?" or "How should the agent have handled the price objection?"</div>'

    chat_js = f"""<script>
const form=document.getElementById('chat-form');
const input=document.getElementById('chat-input');
const btn=document.getElementById('send-btn');
const msgs=document.getElementById('messages');
function addMsg(role,text){{
  const d=document.createElement('div');
  d.className='msg '+role; d.textContent=text;
  msgs.appendChild(d); msgs.scrollTop=msgs.scrollHeight;
}}
form.addEventListener('submit',async e=>{{
  e.preventDefault();
  const text=input.value.trim(); if(!text) return;
  addMsg('user',text); input.value='';
  btn.disabled=true; btn.textContent='…';
  try{{
    const r=await fetch('/calls/{call_id}/chat',{{
      method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{message:text}})
    }});
    const d=await r.json();
    addMsg('assistant',d.reply||d.detail||'Error');
  }}catch(err){{addMsg('assistant','Request failed: '+err.message);}}
  finally{{btn.disabled=false;btn.textContent='Send';input.focus();}}
}});
msgs.scrollTop=msgs.scrollHeight;
</script>"""

    body = f"""
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
  <a href="/" style="color:#64748b;font-size:.875rem;text-decoration:none">← All calls</a>
  <h1 style="margin:0;flex:1">Call — {call.caller_id or call_id}</h1>
  <form method="post" action="/calls/{call_id}/delete"
    onsubmit="return confirm('Delete this call and all its chat history? This cannot be undone.')">
    <button type="submit"
      style="padding:.4rem .85rem;background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;
             border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:600">
      Delete
    </button>
  </form>
</div>
{meta_html}
{barrier_html}
<h2>Chat about this call</h2>
<div id="chat-wrap">
  <div id="messages">{msg_html}</div>
  <form id="chat-form">
    <input id="chat-input" type="text" placeholder="Ask about this call…" autocomplete="off" autofocus>
    <button id="send-btn" type="submit">Send</button>
  </form>
</div>"""

    return page(f"Call — {call.caller_id or call_id}", body, chat_js)
