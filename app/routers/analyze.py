"""Cross-call analysis page with time-range filter and Claude chat."""
from datetime import datetime, timedelta

from anthropic import Anthropic
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..schemas import ChatRequest
from .shared_ui import page

router = APIRouter()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _week_bounds(offset: int = 0):
    """Return (start, end) for the current week minus `offset` weeks."""
    today = datetime.utcnow().date()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
    end = start + timedelta(days=6)
    return datetime(start.year, start.month, start.day), datetime(end.year, end.month, end.day, 23, 59, 59)


@router.get("/analyze", response_class=HTMLResponse)
def analyze_page():
    send_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M5 12l15-7-7 15-2-6-6-2z"/></svg>'
    spark_ico = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/></svg>'
    SUGGESTIONS = [
        "What are the most common reasons callers didn't apply?",
        "Which publisher sends the most qualified callers?",
        "How do agents handle price objections?",
        "What % of calls reached the application step?",
    ]
    suggests_html = "".join(
        f'<button class="suggest-btn" onclick="sendMsg(this.querySelector(\'span\').textContent)">'
        f'{spark_ico}<span>{s}</span></button>'
        for s in SUGGESTIONS
    )
    body = f"""<div style="display:flex;justify-content:center;height:100%">
<div class="ask-wrap">
  <div class="range-bar">
    <select id="range-select">
      <option value="this_week">This week</option>
      <option value="last_week">Last week</option>
      <option value="all">All time</option>
      <option value="custom">Custom range</option>
    </select>
    <span id="custom-dates" style="display:none;gap:6px;align-items:center">
      <input type="date" id="from-date">
      <span style="color:var(--text-3);font-size:12px">to</span>
      <input type="date" id="to-date">
    </span>
    <button class="btn btn-sm" id="apply-btn">Apply</button>
    <span class="call-count-badge" id="call-count"></span>
  </div>
  <div class="chat-scroll" id="chat-scroll">
    <div class="msg-ai"><div class="msg-av">AI</div>
      <div class="bubble-ai">Select a time range and click Apply, then ask me anything about those calls.</div>
    </div>
    <div class="suggest-list">{suggests_html}</div>
  </div>
  <div class="chat-foot">
    <div class="composer" id="composer">
      <textarea id="chat-input" rows="1" placeholder="Ask about these calls…"></textarea>
      <button class="send-btn" id="send-btn" disabled>{send_ico}</button>
    </div>
  </div>
</div>
</div>"""

    js = """<script>
const rangeSelect = document.getElementById('range-select');
const customDates = document.getElementById('custom-dates');
const applyBtn = document.getElementById('apply-btn');
const countEl = document.getElementById('call-count');
const scroll = document.getElementById('chat-scroll');
const inp = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
let currentRange = {range:'this_week'};
let chatHistory = [];
rangeSelect.addEventListener('change', () => {
  customDates.style.display = rangeSelect.value === 'custom' ? 'flex' : 'none';
});
inp.addEventListener('input', () => {
  inp.style.height = 'auto'; inp.style.height = inp.scrollHeight + 'px';
  btn.disabled = !inp.value.trim();
});
inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!btn.disabled) send(); }});
btn.addEventListener('click', send);
applyBtn.addEventListener('click', async () => {
  currentRange = {range: rangeSelect.value};
  if (rangeSelect.value === 'custom') {
    currentRange.from_date = document.getElementById('from-date').value;
    currentRange.to_date = document.getElementById('to-date').value;
  }
  chatHistory = [];
  const params = new URLSearchParams(currentRange);
  const r = await fetch('/analyze/count?' + params);
  const d = await r.json();
  countEl.textContent = d.count + ' calls';
  scroll.innerHTML = '';
  addBubble('ai', 'Loaded ' + d.count + ' calls. What would you like to know?');
});
function addBubble(role, text) {
  const d = document.createElement('div');
  d.className = role === 'user' ? 'msg-user' : 'msg-ai';
  d.innerHTML = role === 'user'
    ? '<div class="bubble-user">' + text + '</div>'
    : '<div class="msg-av">AI</div><div class="bubble-ai">' + text + '</div>';
  scroll.appendChild(d); scroll.scrollTop = scroll.scrollHeight;
}
function sendMsg(text) { inp.value = text; btn.disabled = false; send(); }
function send() {
  const text = inp.value.trim(); if (!text) return;
  addBubble('user', text);
  chatHistory.push({role:'user', content:text});
  inp.value = ''; inp.style.height = 'auto'; btn.disabled = true;
  const dot = document.createElement('div');
  dot.className = 'msg-ai'; dot.id = 'typing';
  dot.innerHTML = '<div class="msg-av">AI</div><div class="typing"><span></span><span></span><span></span></div>';
  scroll.appendChild(dot); scroll.scrollTop = scroll.scrollHeight;
  fetch('/analyze/chat', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({message:text, range:currentRange, history:chatHistory.slice(0,-1)})
  }).then(r => r.json()).then(d => {
    document.getElementById('typing')?.remove();
    const reply = d.reply || d.detail || 'Error';
    addBubble('ai', reply);
    chatHistory.push({role:'assistant', content:reply});
  }).catch(err => {
    document.getElementById('typing')?.remove();
    addBubble('ai', 'Request failed: ' + err.message);
  });
}
</script>"""
    return page("Ask", body, active_nav="analyze", full_bleed=True, extra_js=js)


def _load_calls(db: Session, range_params: dict) -> list[models.Call]:
    q = db.query(models.Call).filter(models.Call.status == "done")
    range_type = range_params.get("range", "this_week")

    if range_type == "this_week":
        start, end = _week_bounds(0)
        q = q.filter(models.Call.created_at >= start, models.Call.created_at <= end)
    elif range_type == "last_week":
        start, end = _week_bounds(1)
        q = q.filter(models.Call.created_at >= start, models.Call.created_at <= end)
    elif range_type == "custom":
        from_date = range_params.get("from_date", "")
        to_date = range_params.get("to_date", "")
        if from_date:
            q = q.filter(models.Call.created_at >= datetime.fromisoformat(from_date))
        if to_date:
            end_dt = datetime.fromisoformat(to_date).replace(hour=23, minute=59, second=59)
            q = q.filter(models.Call.created_at <= end_dt)
    # "all" — no date filter

    return q.order_by(models.Call.created_at.desc()).all()


@router.get("/analyze/count")
def analyze_count(
    range: str = "this_week",
    from_date: str = "",
    to_date: str = "",
    db: Session = Depends(get_db),
):
    calls = _load_calls(db, {"range": range, "from_date": from_date, "to_date": to_date})
    return {"count": len(calls)}


class AnalyzeChatRequest(ChatRequest):
    range: dict = {}
    history: list = []


@router.post("/analyze/chat")
def analyze_chat(req: AnalyzeChatRequest, db: Session = Depends(get_db)):
    calls = _load_calls(db, req.range)
    if not calls:
        return {"reply": "No completed calls found for that time range. Try uploading some calls first."}

    # Build a compact summary of each call for the prompt
    summaries = []
    for c in calls:
        parts = [
            f"Call {c.caller_id or c.call_id}",
            f"buyer={c.buyer}",
            f"publisher={c.publisher}",
        ]
        if c.campaign_name:
            parts.append(f"campaign={c.campaign_name}")
        if c.total_score is not None:
            parts.append(f"score={c.total_score}")
        if c.termination_reason:
            parts.append(f"termination={c.termination_reason}")
        if c.conversion_barrier:
            parts.append(f"barrier={c.conversion_barrier}")
        summaries.append(" | ".join(parts))

    range_label = req.range.get("range", "all time").replace("_", " ")
    system_ctx = (
        f"You are a sales analytics expert. Analyze the following {len(calls)} calls from {range_label}.\n\n"
        f"CALL SUMMARIES:\n" + "\n".join(summaries) + "\n\n"
        f"Answer questions concisely. When asked about top reasons, list them by frequency with examples."
    )

    messages = [
        {"role": "user", "content": system_ctx},
        {"role": "assistant", "content": f"I've reviewed {len(calls)} calls. What would you like to know?"},
    ]
    for m in req.history:
        if isinstance(m, dict):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": req.message})

    response = _get_client().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1000,
        messages=messages,
    )
    return {"reply": response.content[0].text.strip()}
