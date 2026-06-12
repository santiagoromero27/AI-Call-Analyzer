import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..services.notify import send_telegram

router = APIRouter()


@router.post("/tasks/daily-briefing")
def daily_briefing(db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=1)
    calls = (
        db.query(models.Call)
        .filter(models.Call.created_at >= since, models.Call.total_score.isnot(None))
        .all()
    )

    if not calls:
        msg = "📊 Daily Briefing: no calls processed in the last 24 h."
        send_telegram(msg)
        return {"message": msg}

    total = len(calls)
    billable = sum(1 for c in calls if c.billable)
    avg_score = round(sum(c.total_score for c in calls) / total, 1)

    by_pub: dict = {}
    for c in calls:
        p = c.publisher
        if p not in by_pub:
            by_pub[p] = {"count": 0, "billable": 0}
        by_pub[p]["count"] += 1
        if c.billable:
            by_pub[p]["billable"] += 1

    pub_lines = "\n".join(
        f"  {p}: {s['billable']}/{s['count']} billable" for p, s in by_pub.items()
    )

    msg = (
        f"📊 <b>Daily QA Briefing</b> — {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
        f"Calls: {total} | Billable: {billable} ({round(billable / total * 100)}%)\n"
        f"Avg score: {avg_score}/100\n\n"
        f"<b>By publisher:</b>\n{pub_lines}"
    )
    send_telegram(msg)
    return {"calls": total, "billable": billable, "avg_score": avg_score}
