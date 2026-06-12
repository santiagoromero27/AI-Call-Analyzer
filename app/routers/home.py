"""Home page: dashboard stats + call list with search."""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from .shared_ui import page, score_pill

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(q: str = "", db: Session = Depends(get_db)):
    all_calls = db.query(models.Call).order_by(models.Call.created_at.desc()).all()
    scored = [c for c in all_calls if c.total_score is not None]
    pending = [c for c in all_calls if c.status == "pending"]
    total = len(all_calls)
    avg_score = round(sum(c.total_score for c in scored) / len(scored), 1) if scored else 0

    filtered = all_calls
    if q:
        filtered = [c for c in all_calls if q.lower() in (c.caller_id or "").lower()]

    stats = f"""<div class="stat-row">
  <div class="stat-card">
    <div class="sc-label">Total calls</div>
    <div class="sc-value">{total}</div>
    <div class="sc-sub">in this workspace</div>
  </div>
  <div class="stat-card">
    <div class="sc-label">Scored</div>
    <div class="sc-value">{len(scored)}</div>
    <div class="sc-sub">{len(pending)} pending</div>
  </div>
  <div class="stat-card">
    <div class="sc-label">Avg. score</div>
    <div class="sc-value">{avg_score}</div>
    <div class="sc-sub">application likelihood</div>
  </div>
</div>"""

    rows = ""
    for c in filtered:
        score_html = score_pill(c.total_score)
        status_html = '<span class="pill tone-amber">pending</span>' if c.status == "pending" else \
                      '<span class="pill tone-red">failed</span>' if c.status == "failed" else ""
        rows += f"""<tr onclick="location.href='/calls/{c.call_id}'" style="cursor:pointer">
  <td class="mono cell-muted" style="white-space:nowrap">{c.created_at.strftime('%Y-%m-%d %H:%M')}</td>
  <td style="font-weight:500;white-space:nowrap">{c.campaign_name or "—"}</td>
  <td class="cell-muted">{c.publisher}</td>
  <td class="cell-muted">{c.buyer}</td>
  <td class="mono">{c.caller_id or "—"}</td>
  <td class="mono cell-muted">{f"{c.duration_seconds}s" if c.duration_seconds else "—"}</td>
  <td>{score_html}{" " + status_html if status_html else ""}</td>
  <td onclick="event.stopPropagation()" style="width:40px;padding:6px 8px">
    <form method="post" action="/calls/{c.call_id}/delete" onsubmit="return confirm('Delete this call?')">
      <button type="submit" class="btn btn-ghost btn-sm" style="padding:4px 6px;color:var(--text-3)">✕</button>
    </form>
  </td>
</tr>"""

    q_label = f' matching "{q}"' if q else ""
    empty = f'<tr><td colspan="8" style="text-align:center;color:var(--text-3);padding:40px">No calls{q_label}</td></tr>' if not rows else ""

    topbar_extra = """<a href="/analyze" class="btn btn-sm btn-ghost">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M21 11.5a8.4 8.4 0 01-9 8.4L4 21l1.1-3.5A8.5 8.5 0 1121 11.5z"/><circle cx="8.5" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="11.5" r="1" fill="currentColor" stroke="none"/></svg>
  Ask AI
</a>
<a href="/upload" class="btn btn-sm btn-primary" style="margin-left:4px">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M12 16V4"/><path d="M8 8l4-4 4 4"/><path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"/></svg>
  Upload
</a>"""

    body = f"""{stats}
<div class="table-wrap">
  <div class="toolbar">
    <div class="search-box">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>
      <form method="get" style="flex:1;display:flex">
        <input name="q" value="{q}" placeholder="Search caller ID…" style="flex:1">
      </form>
    </div>
    {"" if not q else f'<a href="/" class="btn btn-ghost btn-sm">Clear</a>'}
    <span class="count-label">{len(filtered)} of {total}</span>
  </div>
  <div style="overflow-x:auto">
    <table class="calls">
      <thead><tr>
        <th>Timestamp</th><th>Campaign</th><th>Publisher</th><th>Buyer</th>
        <th>Caller ID</th><th>Length</th><th>Score</th><th></th>
      </tr></thead>
      <tbody>{rows}{empty}</tbody>
    </table>
  </div>
</div>"""

    return page("Calls", body, active_nav="calls", call_count=total,
                topbar_extra=topbar_extra)
