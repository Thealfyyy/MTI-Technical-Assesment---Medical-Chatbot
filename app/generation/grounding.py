"""Deterministic post-generation checks for composed answers.

These checks do not prove semantic entailment. They block an answer that
introduces a number, drug name, brand, or other proper name that does not
appear in the cited passages or the question, so a paraphrased answer cannot
silently add a dose or a medicine the corpus never states. The verbatim
evidence requirement in the generation client supplies the audit trail; the
checks here bound what composed prose is allowed to mention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9'\-\u2019]{3,}")
_SENTENCE_SPLIT = re.compile(r"[.!?؟\n:;]+")

# The corpus contains no Cyrillic, Greek or CJK text, so those letters can never
# be supported by a cited passage. Qwen3 occasionally renders a drug name in
# Cyrillic look-alike letters ("الдиклофенак", "ацидиосис"); the Latin-token
# check below cannot see them because they are neither Arabic nor Latin.
_FOREIGN_SCRIPT = re.compile(r"[\u0370-\u03FF\u0400-\u04FF\u4E00-\u9FFF]+")

# English function words an Arabic answer may legitimately use without the
# corpus containing them. Content words and names are never listed here.
_CONNECTORS = frozenset(
    {
        "about", "after", "also", "and", "any", "are", "before", "between", "both",
        "but", "can", "could", "during", "each", "either", "etc", "for", "from",
        "further", "have", "has", "however", "include", "includes", "including",
        "into", "its", "less", "may", "more", "most", "must", "not", "only",
        "other", "over", "patient", "patients", "per", "should", "since", "some",
        "such", "than", "that", "the", "their", "then", "there", "these", "they",
        "this", "those", "through", "under", "use", "used", "using", "very",
        "was", "were", "what", "when", "where", "which", "while", "who", "with",
        "within", "would",
    }
)


@dataclass
class GroundingCheck:
    """Outcome of the deterministic grounding check."""

    ok: bool
    unsupported: list[str]


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _script_counts(text: str) -> tuple[int, int]:
    return len(_ARABIC_LETTER.findall(text)), len(_LATIN_LETTER.findall(text))


def _capitalized_mid_sentence_tokens(text: str) -> list[str]:
    """Names a reader would notice: capitalized words that are not sentence-initial."""
    tokens: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        words = sentence.split()
        for word in words[1:]:
            cleaned = word.strip("()[]{}\"'،؛")
            if _LATIN_TOKEN.fullmatch(cleaned) and cleaned[:1].isupper():
                tokens.append(cleaned)
    return tokens


def check_answer_grounding(answer: str, evidence_text: str, question: str) -> GroundingCheck:
    """Reject an answer that mentions numbers or names absent from its evidence.

    ``evidence_text`` is the text of the chunks the answer cites, not only the
    quoted spans, so a correct statement drawn from elsewhere in the same
    cited section is not rejected. The question is included because echoing a
    detail the user supplied (for example an age or a dose) is not fabrication.
    """
    answer = answer.strip()
    if not answer:
        return GroundingCheck(False, [""])

    support = _normalize(f"{evidence_text} {question}")
    unsupported: list[str] = []

    for number in _NUMBER.findall(answer):
        if number not in support:
            unsupported.append(number)

    unsupported.extend(run for run in _FOREIGN_SCRIPT.findall(answer) if run.casefold() not in support)

    arabic_letters, latin_letters = _script_counts(answer)
    if arabic_letters > 0 and arabic_letters >= latin_letters:
        # Arabic prose: every Latin token is a drug/clinical name and must exist
        # in the cited passages, so a translation cannot smuggle in a new drug.
        candidates = [
            token for token in _LATIN_TOKEN.findall(answer) if token.casefold() not in _CONNECTORS
        ]
        # Latin tokens are case-insensitive names; compare on the normalized text.
        unsupported.extend(token for token in candidates if token.casefold() not in support)
    else:
        # English prose: sentence-initial capitals are ordinary words, so only
        # proper names that appear mid-sentence are treated as checkable.
        unsupported.extend(
            token
            for token in _capitalized_mid_sentence_tokens(answer)
            if token.casefold() not in _CONNECTORS and token.casefold() not in support
        )

    # Preserve order, drop duplicates.
    unique = list(dict.fromkeys(unsupported))
    return GroundingCheck(not unique, unique)


_OFF_CORPUS_SUBSTANCES = frozenset({
    "viagra", "فياجرا", "sildenafil", "سيلدينافيل",
    "botox", "بوتوكس", "بوتكس",
    "finasteride", "فيناسترايد", "فيناستيريد",
    "remdesivir", "ريمديسيفير", "ريمدسيفير",
    "isotretinoin", "roaccutane", "روأكوتان", "رواكوتان",
    "green tea", "شاي اخضر", "شاي أخضر", "hibiscus", "كركديه", "الكركديه",
    "apple cider", "خل التفاح",
})


def contains_off_corpus_substance(text: str) -> bool:
    """Return True if the text asks about a substance known to be completely absent from the 9-document formulary."""
    lowered = text.casefold()
    return any(sub in lowered for sub in _OFF_CORPUS_SUBSTANCES)

