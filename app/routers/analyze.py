"""Cross-call analysis page with time-range filter and Claude chat."""
import json
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


_ANALYZE_BODY = """
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem">
  <h1 style="margin:0">Cross-call Analysis</h1>
</div>
<div class="card" style="margin-bottom:1.5rem">
  <form id="filter-form" style="display:flex;flex-wrap:wrap;gap:.75rem;align-items:flex-end">
    <label class="field" style="margin:0;flex:0 0 auto">
      Time range
      <select name="range" id="range-select"
        style="margin-top:.3rem;padding:.45rem .75rem;border:1px solid #e2e8f0;border-radius:6px;font-size:.875rem">
        <option value="this_week">This week</option>
        <option value="last_week">Last week</option>
        <option value="custom">Custom range</option>
        <option value="all">All time</option>
      </select>
    </label>
    <span id="custom-fields" style="display:none;display:flex;gap:.5rem;align-items:flex-end">
      <label class="field" style="margin:0">
        From
        <input type="date" name="from_date" id="from_date"
          style="margin-top:.3rem;padding:.45rem .75rem;border:1px solid #e2e8f0;border-radius:6px;font-size:.875rem">
      </label>
      <label class="field" style="margin:0">
        To
        <input type="date" name="to_date" id="to_date"
          style="margin-top:.3rem;padding:.45rem .75rem;border:1px solid #e2e8f0;border-radius:6px;font-size:.875rem">
      </label>
    </span>
    <button class="btn" type="button" id="apply-filter" style="margin-bottom:2px">Apply</button>
  </form>
  <div id="call-count" style="font-size:.8rem;color:#94a3b8;margin-top:.6rem"></div>
</div>
<h2>Ask questions about these calls</h2>
<div id="chat-wrap">
  <div id="messages">
    <div class="msg assistant">Select a time range and click Apply, then ask me anything — e.g. "What are the top 2 reasons callers didn't buy a policy?" or "Which agents had the most failed conversions?"</div>
  </div>
  <form id="chat-form">
    <input id="chat-input" type="text" placeholder="Ask about this batch of calls…" autocomplete="off">
    <button id="send-btn" type="submit">Send</button>
  </form>
</div>
<script>
const rangeSelect=document.getElementById('range-select');
const customFields=document.getElementById('custom-fields');
const applyBtn=document.getElementById('apply-filter');
const countEl=document.getElementById('call-count');
const form=document.getElementById('chat-form');
const input=document.getElementById('chat-input');
const btn=document.getElementById('send-btn');
const msgs=document.getElementById('messages');

let currentRange={range:'this_week'};
let chatHistory=[];

rangeSelect.addEventListener('change',()=>{
  customFields.style.display=rangeSelect.value==='custom'?'flex':'none';
});

function addMsg(role,text){
  const d=document.createElement('div');
  d.className='msg '+role; d.textContent=text;
  msgs.appendChild(d); msgs.scrollTop=msgs.scrollHeight;
}

applyBtn.addEventListener('click',async()=>{
  currentRange={range:rangeSelect.value};
  if(rangeSelect.value==='custom'){
    currentRange.from_date=document.getElementById('from_date').value;
    currentRange.to_date=document.getElementById('to_date').value;
  }
  chatHistory=[];
  // Ask server how many calls are in range
  const params=new URLSearchParams(currentRange);
  const r=await fetch('/analyze/count?'+params);
  const d=await r.json();
  countEl.textContent=d.count+' calls in this range';
  msgs.innerHTML='';
  addMsg('assistant','Loaded '+d.count+' calls. What would you like to know?');
});

form.addEventListener('submit',async e=>{
  e.preventDefault();
  const text=input.value.trim(); if(!text) return;
  addMsg('user',text);
  chatHistory.push({role:'user',content:text});
  input.value=''; btn.disabled=true; btn.textContent='…';
  try{
    const r=await fetch('/analyze/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text,range:currentRange,history:chatHistory.slice(0,-1)})
    });
    const d=await r.json();
    const reply=d.reply||d.detail||'Error';
    addMsg('assistant',reply);
    chatHistory.push({role:'assistant',content:reply});
  }catch(err){addMsg('assistant','Request failed: '+err.message);}
  finally{btn.disabled=false;btn.textContent='Send';input.focus();}
});
</script>
"""


@router.get("/analyze", response_class=HTMLResponse)
def analyze_page():
    return page("Analyze", _ANALYZE_BODY)


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
