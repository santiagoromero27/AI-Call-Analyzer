"""Home page: dashboard stats + full call list with caller ID search."""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from .shared_ui import page, badge_score

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(q: str = "", db: Session = Depends(get_db)):
    all_calls = db.query(models.Call).order_by(models.Call.created_at.desc()).all()

    # Stats over all calls
    scored = [c for c in all_calls if c.total_score is not None]
    total = len(all_calls)
    avg_score = round(sum(c.total_score for c in scored) / len(scored), 1) if scored else 0

    # Filter by caller ID search
    filtered = all_calls
    if q:
        filtered = [c for c in all_calls if q.lower() in (c.caller_id or "").lower()]

    stats_html = f"""
<div class="stat-grid">
  <div class="stat"><div class="stat-label">Total calls</div><div class="stat-value">{total}</div></div>
  <div class="stat"><div class="stat-label">Scored</div><div class="stat-value">{len(scored)}</div></div>
  <div class="stat"><div class="stat-label">Avg score</div><div class="stat-value">{avg_score}</div></div>
</div>"""

    rows = ""
    for c in filtered:
        rows += f"""<tr onclick="location='/calls/{c.call_id}'" style="cursor:pointer">
<td>{c.caller_id or "—"}</td>
<td>{c.publisher}</td>
<td>{c.buyer}</td>
<td>{c.campaign_name or "—"}</td>
<td>{c.termination_reason or "—"}</td>
<td>{badge_score(c.total_score)}</td>
<td style="color:#94a3b8;font-size:.8rem">{c.created_at.strftime('%b %d %H:%M')}</td>
<td onclick="event.stopPropagation()">
  <form method="post" action="/calls/{c.call_id}/delete"
    onsubmit="return confirm('Delete this call?')">
    <button type="submit"
      style="padding:.2rem .6rem;background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;
             border-radius:4px;cursor:pointer;font-size:.75rem;font-weight:600">
      ✕
    </button>
  </form>
</td>
</tr>"""

    q_label = f' matching "{q}"' if q else ""
    no_results = "" if rows else f'<tr><td colspan="8" style="text-align:center;color:#94a3b8;padding:2rem">No calls{q_label}</td></tr>'

    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem">
  <h1 style="margin:0">Calls</h1>
  <a class="btn" href="/upload">+ Upload</a>
</div>
{stats_html}
<form method="get" style="margin-bottom:1rem;display:flex;gap:.5rem">
  <input type="text" name="q" value="{q}"
    placeholder="Search caller ID…"
    style="flex:1;max-width:320px;padding:.45rem .75rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem">
  <button class="btn" type="submit">Search</button>
  {"<a href='/' class='btn' style='background:#64748b'>Clear</a>" if q else ""}
</form>
<table>
<thead><tr>
  <th>Caller ID</th><th>Publisher</th><th>Buyer</th><th>Campaign</th>
  <th>Termination</th><th>Score</th><th>Date</th>
</tr></thead>
<tbody>{rows}{no_results}</tbody>
</table>"""

    return page("Calls", body)
