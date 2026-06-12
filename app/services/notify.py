"""Send Telegram alerts for scored calls."""
import requests

from ..config import settings


def send_telegram(text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def format_call_alert(call_id: str, publisher: str, buyer: str, result: dict) -> str:
    billable_flag = "✅ BILLABLE" if result.get("billable") else "❌ NOT BILLABLE"
    score = result.get("total_score", 0)
    summary = result.get("summary", "")

    evidence_lines = []
    for name, data in result.get("criteria_scores", {}).items():
        ev = data.get("evidence", "").strip()
        if ev:
            evidence_lines.append(f"  • <b>{name}</b>: {ev}")

    evidence_block = "\n".join(evidence_lines[:5])

    return (
        f"{billable_flag}\n"
        f"Call: <code>{call_id}</code>\n"
        f"Publisher: {publisher} | Buyer: {buyer}\n"
        f"Score: <b>{score}/100</b>\n\n"
        f"{summary}\n\n"
        f"<b>Evidence:</b>\n{evidence_block}"
    )
