from __future__ import annotations

from datetime import date
from typing import Any

from .text_normalizer import clean_text, flatten_value
from .utils import clamp, safe_float


def _bool_score(value: Any, positive: float, negative: float) -> float | None:
    return positive if value is True else negative if value is False else None


def build_hireability_profile(
    fingerprint: dict[str, Any],
    neutral_score: float = 0.50,
) -> dict[str, Any]:
    behavior = fingerprint.get("behavioral_signal_summary") or {}
    availability = fingerprint.get("availability_signal_summary") or {}
    text = clean_text(
        f"{flatten_value(behavior)} {flatten_value(availability)} "
        f"{fingerprint.get('raw_text_compact', '')}"
    )
    missing: list[str] = []
    positive: list[str] = []
    negative: list[str] = []

    response = safe_float(behavior.get("recruiter_response_rate")) if isinstance(behavior, dict) else None
    response_score = clamp(response) if response is not None else neutral_score
    if response is None:
        missing.append("response_rate")
    elif response >= 0.65:
        positive.append("high_response")
    elif response < 0.15:
        negative.append("low_response")

    activity_score = neutral_score
    last_active = behavior.get("last_active_date") if isinstance(behavior, dict) else None
    try:
        days = (date.today() - date.fromisoformat(str(last_active)[:10])).days
        activity_score = clamp(1.0 - days / 365.0)
        (positive if days <= 45 else negative if days > 180 else []).append("active_recently" if days <= 45 else "inactive")
    except (TypeError, ValueError):
        missing.append("last_active_date")

    open_to_work = availability.get("open_to_work_flag") if isinstance(availability, dict) else None
    availability_score = _bool_score(open_to_work, 1.0, 0.35)
    if availability_score is None:
        availability_score = neutral_score
        missing.append("open_to_work")
    elif open_to_work:
        positive.append("open_to_work")
    else:
        negative.append("not_open_to_work")

    interview = safe_float(behavior.get("interview_completion_rate")) if isinstance(behavior, dict) else None
    interview_score = clamp(interview) if interview is not None else neutral_score
    if interview is None:
        missing.append("interview_completion")
    elif interview >= 0.75:
        positive.append("interview_ready")

    relocate = availability.get("willing_to_relocate") if isinstance(availability, dict) else None
    relocation_score = _bool_score(relocate, 0.9, 0.45)
    if relocation_score is None:
        relocation_score = 0.55 if "relocat" not in text else 0.8
        missing.append("relocation")
    elif relocate:
        positive.append("relocation_flexible")
    else:
        negative.append("not_willing_to_relocate")

    notice = safe_float(availability.get("notice_period_days")) if isinstance(availability, dict) else None
    notice_score = clamp(1.0 - notice / 180.0) if notice is not None else neutral_score
    if notice is None:
        missing.append("notice_period")
    elif notice <= 30:
        positive.append("short_notice")
    elif notice >= 90:
        negative.append("long_notice")

    phrase_positive = ("actively looking", "available immediately", "serving notice", "open to work")
    phrase_negative = ("not looking", "unavailable")
    positive.extend(term for term in phrase_positive if term in text)
    negative.extend(term for term in phrase_negative if term in text)

    score = clamp(
        0.25 * response_score
        + 0.15 * activity_score
        + 0.20 * availability_score
        + 0.15 * interview_score
        + 0.10 * relocation_score
        + 0.15 * notice_score
    )
    notes = [
        f"Response signal {response_score:.2f}; activity {activity_score:.2f}; "
        f"availability {availability_score:.2f}; notice {notice_score:.2f}."
    ]
    return {
        "candidate_id": str(fingerprint.get("candidate_id") or ""),
        "hireability_score": round(score, 4),
        "response_signal_score": round(response_score, 4),
        "activity_signal_score": round(activity_score, 4),
        "availability_score": round(availability_score, 4),
        "interview_readiness_score": round(interview_score, 4),
        "relocation_flexibility_score": round(relocation_score, 4),
        "notice_period_score": round(notice_score, 4),
        "missing_behavior_signals": missing,
        "positive_hireability_signals": list(dict.fromkeys(positive)),
        "negative_hireability_signals": list(dict.fromkeys(negative)),
        "hireability_notes": notes,
    }
