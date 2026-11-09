"""Egyptian Dialect and Franco-Arabic (Arabizi) Normalizer.

Provides deterministic transliteration and lexical expansion for Franco-Arabic queries
(e.g., '7omo2a' -> 'حموضة', 'katably' -> 'كتبلي', 'soda3' -> 'صداع') and preserves
English drug brand names for exact lexical matching.
"""

from __future__ import annotations

import re
import unicodedata

# Common Franco-Arabic character map
FRANCO_CHAR_MAP: dict[str, str] = {
    "2": "ء",
    "3": "ع",
    "4": "ش",
    "5": "خ",
    "6": "ط",
    "7": "ح",
    "8": "غ",
    "9": "ص",
}

# High-frequency Egyptian Franco medical & conversational vocabulary
FRANCO_VOCAB_MAP: dict[str, str] = {
    # Symptoms & Conditions
    "7omo2a": "حموضة",
    "7omoda": "حموضة",
    "homo2a": "حموضة",
    "homoda": "حموضة",
    "7or2an": "حرقان",
    "soda3": "صداع",
    "soda": "صداع",
    "maghs": "مغص",
    "maghss": "مغص",
    "so5ona": "سخونة",
    "so5oona": "سخونة",
    "tergee3": "ترجيع",
    "targee3": "ترجيع",
    "qay2": "قيء",
    "2ay2": "قيء",
    "rebo": "ربو",
    "el-rebo": "الربو",
    "elrebo": "الربو",
    "hasaseya": "حساسية",
    "7asaseya": "حساسية",
    "qoloon": "قولون",
    "el-qoloon": "القولون",
    "elqoloon": "القولون",
    "sokar": "سكر",
    "el-sokar": "السكر",
    "elsokar": "السكر",
    "daght": "ضغط",
    "el-daght": "الضغط",
    "eldaght": "الضغط",
    "koleystrol": "كوليسترول",
    "kolestrol": "كوليسترول",
    "waga3": "وجع",
    "alam": "ألم",
    "2alam": "ألم",
    "eltahab": "التهاب",
    "el-tahab": "التهاب",
    "zour": "زور",
    "halq": "حلق",
    "7al2": "حلق",
    "ma3eda": "معدة",
    "el-ma3eda": "المعدة",
    "elma3eda": "المعدة",
    # Common Egyptian dialect verbs & questions
    "katably": "كتبلي",
    "katablo": "كتبله",
    "doctor": "دكتور",
    "doktor": "دكتور",
    "dr": "دكتور",
    "3ashan": "عشان",
    "3ashn": "عشان",
    "sa7": "صح",
    "moshkela": "مشكلة",
    "feeh": "فيه",
    "fih": "فيه",
    "eh": "إيه",
    "ezay": "إزاي",
    "a5do": "آخده",
    "a5od": "آخد",
    "a5odha": "آخدها",
    "yenfa3": "ينفع",
    "mayenfa3sh": "ماينفعش",
    "mafeesh": "مفيش",
    "3andi": "عندي",
    "3andy": "عندي",
    "law": "لو",
    "wala": "ولا",
    "momken": "ممكن",
    "awy": "أوي",
    "gamda": "جامدة",
    "shadeeda": "شديدة",
    "keda": "كده",
    "kda": "كده",
    "tab": "طب",
    "da": "ده",
    "di": "دي",
    "howa": "هو",
    "heya": "هي",
    "m3a": "مع",
    "ma3": "مع",
    "aktar": "أكتر",
    "a2al": "أقل",
    "dawa": "دواء",
    "el-dawa": "الدواء",
    "eldawa": "الدواء",
    "3elag": "علاج",
    "gora3": "جرعة",
    "gor3a": "جرعة",
    "agras": "أقراص",
    "fowar": "فوار",
}


def is_likely_franco(text: str) -> bool:
    """Determine whether the text contains Franco-Arabic patterns (digits inside words, etc.)."""
    # Contains digits 2, 3, 5, 7 in the middle of latin words
    if re.search(r"[a-zA-Z]+[23578][a-zA-Z]*|[23578][a-zA-Z]+", text):
        return True
    # Contains high-frequency Franco vocabulary tokens
    words = re.findall(r"\b[a-zA-Z0-9\'-]+\b", text.lower())
    match_count = sum(1 for w in words if w in FRANCO_VOCAB_MAP)
    return match_count >= 2 or (match_count >= 1 and any(c in "23578" for c in text))


def normalize_franco_to_arabic(query: str) -> str:
    """Expand and transliterate Franco-Arabic tokens to Modern Standard / Egyptian Arabic.

    Returns the query with Franco tokens mapped to Arabic, while preserving English brand names.
    """
    if not is_likely_franco(query):
        return query

    tokens = query.split()
    translated_tokens: list[str] = []

    for token in tokens:
        clean_token = token.strip(".,?!:;\"'()").lower()
        # Direct dictionary match
        if clean_token in FRANCO_VOCAB_MAP:
            translated_tokens.append(FRANCO_VOCAB_MAP[clean_token])
            continue

        # Check prefixed 'el-' or 'al-'
        if clean_token.startswith("el-") and clean_token[3:] in FRANCO_VOCAB_MAP:
            translated_tokens.append("ال" + FRANCO_VOCAB_MAP[clean_token[3:]])
            continue
        if clean_token.startswith("al-") and clean_token[3:] in FRANCO_VOCAB_MAP:
            translated_tokens.append("ال" + FRANCO_VOCAB_MAP[clean_token[3:]])
            continue

        # Transliterate numbers if token has franco digits
        if any(d in clean_token for d in "23456789"):
            t = clean_token
            for digit, char in FRANCO_CHAR_MAP.items():
                t = t.replace(digit, char)
            translated_tokens.append(t)
        else:
            translated_tokens.append(token)

    return " ".join(translated_tokens)


def extract_keywords_for_lexical_search(query: str) -> list[str]:
    """Extract distinct keywords (Arabic and English) from a query for BM25/keyword search."""
    tokens = re.findall(r"[\u0600-\u06FF\w\-]+", query)
    # Filter very short stop tokens
    stop_tokens = {
        "في", "من", "على", "إلى", "عن", "مع", "أو", "هل", "ما", "هو", "هي", "ده", "دي", "إيه",
        "in", "on", "at", "to", "for", "with", "a", "an", "the", "is", "are", "of", "and", "or",
    }
    keywords = [t for t in tokens if len(t) > 1 and t.lower() not in stop_tokens]
    return keywords
