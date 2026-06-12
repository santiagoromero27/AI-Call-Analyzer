"""Score a call transcript against a buyer rubric using Claude.

The primary output is not just a rubric score but a diagnosis of WHY the call
did not close.  Every result includes a `conversion_barrier` field that names
the single most important obstacle with a timestamped quote from the transcript.
"""
import json
import os

from anthropic import Anthropic

from ..config import settings

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _load_rubric(buyer: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "rubrics", "buyers.json")
    with open(path) as f:
        rubrics = json.load(f)
    return rubrics.get(buyer, rubrics["default"])


def _format_transcript(segments: list[dict]) -> str:
    return "\n".join(
        f"[{s['start']:.1f}s] {s['speaker'].upper()}: {s['text']}"
        for s in segments
    )


def score_call(
    segments: list[dict],
    buyer: str,
    termination_reason: str = "",
    no_payout_reason: str = "",
) -> dict:
    rubric = _load_rubric(buyer)
    transcript_text = _format_transcript(segments)

    criteria_text = "\n".join(
        f"- {c['name']} (weight {c['weight']}): {c['description']}"
        for c in rubric["criteria"]
    )

    meta_lines = []
    if termination_reason:
        meta_lines.append(f"Termination reason: {termination_reason}")
    if no_payout_reason:
        meta_lines.append(f"No-payout reason (platform): {no_payout_reason}")
    termination_ctx = ("\n" + "\n".join(meta_lines)) if meta_lines else ""

    prompt = f"""You are an insurance sales QA analyst. Your job is to score this call on how likely it was to result in a submitted application — meaning the caller provided payment information and the agent completed the application.

A score of 100 means the caller was qualified, engaged, agreed to apply, and payment/application details were collected. A score of 0 means the call had no realistic path to an application.

TRANSCRIPT:{termination_ctx}
{transcript_text}

RUBRIC — score each criterion 0-100:
{criteria_text}

Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "criteria_scores": {{
    "<criterion_name>": {{
      "score": <0-100>,
      "rationale": "<one sentence>",
      "evidence": "<[Xs] SPEAKER: exact quote>"
    }}
  }},
  "total_score": <weighted average>,
  "summary": "<1-2 sentence summary of how close this call came to a submitted application and why>",
  "conversion_barrier": "<The single most important reason this call did not result in a submitted application. Name the exact moment it stalled — quote it with its timestamp — and state precisely what the agent should have said or done to get to payment collection. Be specific; never say 'poor closing skills'.>"
}}"""

    response = _get_client().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    result = json.loads(raw.strip())

    # Recalculate total_score server-side so it can't be hallucinated
    criteria = rubric["criteria"]
    total_weight = sum(c["weight"] for c in criteria)
    weighted_sum = sum(
        result["criteria_scores"].get(c["name"], {}).get("score", 0) * c["weight"]
        for c in criteria
    )
    result["total_score"] = round(weighted_sum / total_weight, 1) if total_weight else 0
    result.pop("billable", None)

    return result
