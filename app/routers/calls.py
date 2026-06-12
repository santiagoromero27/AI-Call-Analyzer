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
from .shared_ui import page, score_pill

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

    # Parse transcript
    segments = json.loads(call.transcript) if call.transcript else []

    # Metadata grid
    def mc(k, v, mono=False):
        mono_cls = ' style="font-family:var(--mono);font-size:12.5px"' if mono else ""
        return f'<div class="meta-cell"><div class="k">{k}</div><div class="v"{mono_cls}>{v or "—"}</div></div>'

    dur = f"{call.duration_seconds}s" if call.duration_seconds else "—"
    meta_html = f"""<div class="meta-grid">
  {mc("Timestamp", call.created_at.strftime("%Y-%m-%d %H:%M"), mono=True)}
  {mc("Caller ID", call.caller_id, mono=True)}
  {mc("Campaign", call.campaign_name)}
  {mc("Length", dur, mono=True)}
  {mc("Publisher", call.publisher)}
  {mc("Buyer", call.buyer)}
  {mc("Termination", call.termination_reason)}
  {mc("No-payout reason", call.no_payout_reason)}
</div>"""

    # AI summary section
    score_data = json.loads(call.score_json) if call.score_json else {}
    summary_text = score_data.get("summary", "") or call.conversion_barrier or ""
    barrier_text = call.conversion_barrier or ""
    if call.status == "pending":
        ai_html = '<div style="color:var(--text-3);font-size:13px;padding:14px 0">Processing… check back in a moment.</div>'
    elif summary_text:
        barrier_line = f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid #e6e6f6;font-size:13px;color:var(--text-2)"><strong style="color:#854d0e">Why it didn\'t close:</strong> {barrier_text}</div>' if barrier_text and barrier_text != summary_text else ""
        ai_html = f"""<div class="ai-summary">
  <div class="ai-head"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/></svg>Generated from transcript</div>
  {summary_text}{barrier_line}
</div>"""
    else:
        ai_html = ""

    # Transcript
    transcript_html = ""
    if segments:
        utts = ""
        for s in segments:
            speaker = s.get("speaker", "unknown")
            t = s.get("start", 0)
            mins, secs = divmod(int(t), 60)
            t_str = f"{mins}:{secs:02d}"
            utts += f"""<div class="utt">
  <div class="who {speaker}">{speaker.title()}<div class="utime">{t_str}</div></div>
  <div class="txt">{s.get("text","")}</div>
</div>"""
        transcript_html = f'<div class="transcript-wrap">{utts}</div>'

    # Chat history
    history = (db.query(models.ChatMessage)
               .filter(models.ChatMessage.call_db_id == call.id)
               .order_by(models.ChatMessage.created_at).all())

    SUGGESTIONS = [
        "Summarize this call in one line",
        "What objections did the caller raise?",
        "Why did the call end this way?",
        "What should the agent have done differently?",
    ]
    spark_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/></svg>'
    send_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M5 12l15-7-7 15-2-6-6-2z"/></svg>'

    suggests_html = "".join(
        f'<button class="suggest-btn" onclick="sendMsg(this.querySelector(\'span\').textContent)">'
        f'{spark_ico}<span>{s}</span></button>'
        for s in SUGGESTIONS
    )

    msgs_html = ""
    if not history:
        msgs_html = f'<div class="msg-ai"><div class="msg-av">AI</div><div class="bubble-ai">Ask me anything about this call. Try a suggestion below.</div></div><div class="suggest-list">{suggests_html}</div>'
    else:
        for m in history:
            if m.role == "user":
                msgs_html += f'<div class="msg-user"><div class="bubble-user">{m.content}</div></div>'
            else:
                msgs_html += f'<div class="msg-ai"><div class="msg-av">AI</div><div class="bubble-ai">{m.content}</div></div>'

    chat_panel = f"""<div class="detail-sidebar">
<div class="chat-panel">
  <div class="chat-head">
    <div>
      <div class="chat-head-title">Chat with this call</div>
      <div class="chat-head-sub">Scoped to this recording</div>
    </div>
  </div>
  <div class="chat-scroll" id="chat-scroll">{msgs_html}</div>
  <div class="chat-foot">
    <div class="composer" id="composer">
      <textarea id="chat-input" rows="1" placeholder="Ask about this call…"></textarea>
      <button class="send-btn" id="send-btn" disabled>{send_ico}</button>
    </div>
  </div>
</div>
</div>"""

    title_pill = score_pill(call.total_score)
    breadcrumb = f'<span class="crumb" onclick="location.href=\'/\'" style="cursor:pointer">Calls</span><span class="crumb-sep"> / </span><span>{call.caller_id or call_id}</span>'

    main_body = f"""<div class="detail-title">
  {call.caller_id or call_id} {title_pill}
  <form method="post" action="/calls/{call_id}/delete"
    onsubmit="return confirm('Delete this call and all chat history?')" style="margin-left:auto">
    <button type="submit" class="btn btn-danger btn-sm">Delete</button>
  </form>
</div>
{meta_html}
<div class="section-title">{spark_ico} AI Summary</div>
{ai_html}
{"<div class='section-title'>Transcript</div>" + transcript_html if transcript_html else ""}"""

    body = f'<div class="detail-grid"><div class="detail-main">{main_body}</div>{chat_panel}</div>'

    chat_js = f"""<script>
const inp = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
const scroll = document.getElementById('chat-scroll');
inp.addEventListener('input', () => {{
  inp.style.height = 'auto';
  inp.style.height = inp.scrollHeight + 'px';
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
  scroll.appendChild(d);
  scroll.scrollTop = scroll.scrollHeight;
}}
function send() {{
  const text = inp.value.trim(); if (!text) return;
  addBubble('user', text); inp.value = ''; inp.style.height = 'auto';
  btn.disabled = true;
  const dot = document.createElement('div');
  dot.className = 'msg-ai'; dot.id = 'typing';
  dot.innerHTML = '<div class="msg-av">AI</div><div class="typing"><span></span><span></span><span></span></div>';
  scroll.appendChild(dot); scroll.scrollTop = scroll.scrollHeight;
  fetch('/calls/{call_id}/chat', {{
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
        f"Call — {call.caller_id or call_id}", body,
        active_nav="calls", full_bleed=True,
        breadcrumb=breadcrumb, extra_js=chat_js,
    )
