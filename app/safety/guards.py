"""Deterministic pre-generation safety checks and language helpers."""

from __future__ import annotations

import re
from enum import Enum


class SafetyOutcome(str, Enum):
    SAFE = "safe"
    ESCALATE = "escalated"


_EMERGENCY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\boverdose\b|\bpoison(?:ing)?\b|\bswallowed\s+(?:a\s+)?(?:whole\s+)?bottle\b",
        r"\bsevere\s+(?:shortness|difficulty|trouble)\s+of\s+breath\b|\bcan'?t\s+breathe\b|\bblue\s+lips\b|\bcyanosis\b",
        r"\bchest\s+pain\b.{0,40}\bsevere\b|\bsevere\b.{0,40}\bchest\s+pain\b",
        r"\bself[- ]harm\b|\bsuicid(?:e|al)\b|\bkill\s+myself\b",
        r"جرعة\s*زائدة|تسمم|بلع.{0,30}(?:علبة|ازازة|زجاجة)|ضيق\s*نفس\s*شديد|شفايف.{0,15}(?:زرقا|زرقاء)|زرقة|انتحار|إيذاء\s*النفس",
        r"(?:dya2|deya2)\s*nafas.{0,30}(?:shadeed|shadid)|shafayef.{0,20}zor2|bal3.{0,20}(?:3elba|azaza)|gor3a\s*zayeda",
    )
)

_PERSONAL_DOSE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhow\s+many\s*(?:mg|milligrams?|ml|milliliters?)\b",
        r"\b(?:what|which)\s+(?:is\s+)?(?:the\s+)?(?:maximum\s+)?dose\b|\bdosage\s+(?:for|of)\b",
        r"\bhow\s+much\s+(?:should|can|do)\s+(?:i|we|he|she|they|an? adult|a child)\s+(?:take|give)\b",
        r"كام\s*(?:مجم|ملجم|مل|سم)|جرعة\s*(?:كام|قد\s*ايه)|أديه\s*كام|اديه\s*كام|أديله\s*كام",
        r"(?:a5od|akhod|adeelo|adelo).{0,30}(?:kam|mg|ml|sama)",
    )
)


def classify_safety(message: str) -> SafetyOutcome:
    """Escalate urgent red flags and patient-specific dose requests before retrieval/LLM."""
    if any(pattern.search(message) for pattern in _EMERGENCY_PATTERNS + _PERSONAL_DOSE_PATTERNS):
        return SafetyOutcome.ESCALATE
    return SafetyOutcome.SAFE


def detect_answer_language(text: str) -> str:
    """Choose the API language label from the returned answer text's scripts."""
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_arabic and has_latin:
        return "mixed"
    return "ar" if has_arabic else "en"


def response_language_for_query(message: str) -> str:
    """Select a safe static response language for abstention/escalation messages."""
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", message))
    has_latin = bool(re.search(r"[A-Za-z]", message))
    # Franco-Arabic is written in Latin but the intended language is Arabic.
    from app.retrieval.franco_normalizer import is_likely_franco

    if is_likely_franco(message):
        return "ar"
    if has_arabic and has_latin:
        return "mixed"
    return "ar" if has_arabic else "en"
