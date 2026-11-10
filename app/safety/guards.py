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
        r"\bcrushing\s+chest\s+pain\b|\bchest\s+pain\b.{0,40}\b(?:severe|radiat|sweat|arm|jaw)\b|\b(?:severe|radiat)\b.{0,40}\bchest\s+pain\b",
        r"\bself[- ]harm\b|\bsuicid(?:e|al)\b|\bkill\s+myself\b",
        r"\b(?:vomiting|threw\s+up)\s+(?:bright\s+)?red\s+blood\b|\bblack\s+tarry\s+stool\b|\bmelena\b",
        r"\b(?:facial\s+drooping|arm\s+weakness|slurred\s+speech)\b",
        r"\bworst\s+headache\s+of\s+(?:my\s+)?life\b.{0,30}\bstiff\s+neck\b",
        r"\bbarking\s+cough\b.{0,30}\bstridor\b",
        r"\bblistering\s+(?:skin\s+)?detachment\b|\btoxic\s+epidermal\b|\bstevens[- ]johnson\b",
        r"\bheart\s+is\s+beating\s+at\s+\d{3}\b",
        r"\b(?:throat\s+is\s+swelling|lips\s+are\s+blue)\b",
        r"\bsudden\s+loss\s+of\s+vision\b.{0,30}\beye\s+pain\b",
        r"\bsevere\s+testicular\s+pain\b",
        r"\b(?:infant|baby|child|daughter|son).{0,30}\b(?:ingested|swallowed|drank)\b",
        r"\b(?:pregnant|pregnancy)\b.{0,40}\b(?:1[6-9]\d/[1-9]\d{2}|180/|headache|vision|epigastric)\b",
        r"\bby\s+mistake\b|بالغلط|عن\s*طريق\s*الخطأ",
        r"(?:infant|neonate|baby|رضيع|طفل\s*رضيع).{0,40}(?:40|41|حرارت|fever|letharg|مش\s*بيرضع)",
        r"(?:7amel|حامل).{0,50}(?:ينفع|a5od|akhod|اخود|اخد)",
        r"جرعة\s*زائدة|تسمم|بلع.{0,30}(?:علبة|ازازة|زجاجة|شريط)|ضيق\s*نفس\s*شديد|شفايف.{0,15}(?:زرقا|زرقاء)|زرقة|انتحار|إيذاء\s*النفس",
        r"وجع.{0,20}صدري.{0,40}(?:شمال|كتف|دراع|عرقان)|ألم.{0,20}صدري.{0,40}(?:شمال|كتف|دراع|عرقان)",
        r"بيرجع\s*دم|قيء\s*دموي|براز\s*أسود|برازه\s*اسود",
        r"(?:نص\s*وش|وجه).{0,20}(?:معوج|ساقط)|(?:ايده|يده).{0,20}(?:وقعت|ثقيلة)|مش\s*عارف\s*(?:ينطق|يتكلم)",
        r"اسوأ\s*صداع.{0,30}رقب|صداع\s*مفاجئ\s*عنيف.{0,30}رقب",
        r"كحة\s*نباحية.{0,20}بيزيق|صدره\s*بيتحفر",
        r"تقشر\s*في\s*الجلد|فقاقيع\s*في\s*(?:كل\s*)?الجسم",
        r"قلبي\s*بيدق\s*بسرعة.{0,30}(?:دوخة|هقع|اغمى)",
        r"شفايفي\s*و.*ورموا|زوري\s*قافل",
        r"فقدان\s*مفاجئ\s*لل(?:رؤية|نظر)",
        r"(?:ألم|وجع)\s*(?:حاد|شديد).{0,20}الخصية",
        r"سكر(?:ه)?\s*(?:اقل\s*من|تحت|\:|\=)?\s*(?:[1-5]\d)\b|غيبوبة\s*سكر",
        r"حامل.{0,30}(?:180/|170/|160/|تسمم\s*حمل|زغللة)",
        r"ازمة\s*ربو\s*خانقة.{0,30}مش\s*جايب\s*نتيجة",
        r"(?:dya2|deya2)\s*nafas.{0,30}(?:shadeed|shadid)|shafayef.{0,20}zor2|bal3.{0,20}(?:3elba|azaza|shareet)|gor3a\s*zayeda",
        r"alam\s*f\s*sadry.{0,30}(?:shemal|draby|dra3y|3ara2an)",
        r"wesh.{0,20}(?:3weeg|3weg)|eedo\s*wa23et|msh\s*3aref\s*ytkalem",
        r"shafayfy.{0,20}wermo|zory\s*2afel",
    )
)

_PERSONAL_DOSE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhow\s+many\s*(?:mg|milligrams?|ml|milliliters?|puffs?|drops?|tablets?|capsules?)\b",
        r"\b(?:what|which)\s+(?:is\s+)?(?:the\s+)?(?:maximum\s+)?dose\b|\bdosage\s+(?:for|of)\b",
        r"\bhow\s+much\s+(?:should|can|do)\s+(?:i|we|he|she|they|an? adult|a child|my child|my son|my daughter)\s+(?:take|give)\b",
        r"\bhow\s+much\b.{0,35}\b(?:should|can|do)\s+(?:i|we|he|she)\s+(?:give|take)\b",
        r"\bcan\s+i\s+(?:increase|decrease|double|stop|change)\s+my\s+dose\b",
        r"\bshould\s+i\s+(?:stop|discontinue|take)\s+(?:taking\s+)?(?:lipitor|concor|atorvastatin|statin)\b",
        r"ك[ا]?م\s*(?:مجم|ملجم|مل|سم)|جرعة\s*(?:ك[ا]?م|قد\s*ايه)|أديه\s*ك[ا]?م|اديه\s*ك[ا]?م|أديله\s*ك[ا]?م|اديله\s*ك[ا]?م",
        r"ينفع\s*(?:ازود|اوقف|اقلل)\s*جرعة|اوقف.{0,15}ولا\s*اكمل",
        r"(?:a5od|akhod|adeelo|adelo).{0,30}(?:kam|mg|ml|sama)",
        # "الجرعة بتاعة كونترولوك كام في اليوم": a personal dose question where
        # the drug name sits between "dose" and "how much".
        r"(?:ال)?جرعة.{0,40}(?:ك[ا]?م|قد\s*ايه)",
        r"وزنه.{0,20}كيلو.{0,30}(?:ك[ا]?م\s*سم|جرعة)",
    )
)

_DISEASE_SYMPTOMS_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:اعراض|أعراض)\s+(?:مرض\s+)?(?:السكر|الربو|الضغط|الالتهاب الرئوي|القولون العصبي|القولون|سرطان|قرحة)\b",
        r"\b(?:اعراض|أعراض)\s+مرض\b",
        r"\ba3rad\s+mara[d]?\s+el\b",
        r"\ba3rad\s+(?:el\s+)?(?:sokar|rebo|dya2\s*nafas|daya2\s*nafas|colon)\b",
        r"\bsymptoms\s+of\s+(?:diabetes|asthma|copd|pneumonia|hypertension|ibs|arthritis|ulcer|malaria|cancer|peptic\s+ulcer)\b",
        r"\bhow\s+to\s+diagnose\b|\bdiagnos(?:tic|is)\s+(?:symptoms|procedure|criteria)\b",
        r"\b(?:كيف|طريقة)\s+(?:تشخيص|يتم\s+تشخيص)\b",
        r"\bwhat\s+causes\s+(?:hypertension|diabetes|asthma|copd|ulcer|cancer)\b",
        r"\b(?:اسباب|أسباب)\s+(?:ارتفاع\s+ضغط|السكر|الربو|القرحة)\b",
        r"\bhow\s+to\s+perform\s+cpr\b|\bcpr\s+on\b",
    )
)


def is_disease_symptom_query(message: str) -> bool:
    """Return True if the query asks about disease symptoms/diagnosis rather than drug side effects."""
    # Exclude queries that explicitly specify drug side effects
    if re.search(r"جانبي|جانبية|side[\s-]?effects?|adverse|ganb(?:ey|iy)a", message, re.IGNORECASE):
        return False
    from app.retrieval.franco_normalizer import normalize_franco_to_arabic

    normalized = normalize_franco_to_arabic(message)
    for candidate in dict.fromkeys((message, normalized)):
        if any(pattern.search(candidate) for pattern in _DISEASE_SYMPTOMS_PATTERNS):
            return True
    return False


def is_emergency(message: str) -> bool:
    """Return True if the query indicates an acute medical emergency."""
    from app.retrieval.franco_normalizer import normalize_franco_to_arabic

    normalized = normalize_franco_to_arabic(message)
    for candidate in dict.fromkeys((message, normalized)):
        if any(pattern.search(candidate) for pattern in _EMERGENCY_PATTERNS):
            return True
    return False


def is_personal_dose(message: str) -> bool:
    """Return True if the query requests personal dosage adjustment or child dosing."""
    from app.retrieval.franco_normalizer import normalize_franco_to_arabic

    normalized = normalize_franco_to_arabic(message)
    for candidate in dict.fromkeys((message, normalized)):
        if any(pattern.search(candidate) for pattern in _PERSONAL_DOSE_PATTERNS):
            return True
    return False


def classify_safety(message: str) -> SafetyOutcome:
    """Escalate urgent red flags and patient-specific dose requests before retrieval/LLM."""
    if is_emergency(message) or is_personal_dose(message):
        return SafetyOutcome.ESCALATE
    return SafetyOutcome.SAFE


def detect_answer_language(text: str) -> str:
    """Choose the API language label from the dominant script of the answer prose.

    Arabic answers routinely name drugs and tests in Latin script, which the
    assessment's own example response does while still being labelled ``ar``.
    The label therefore counts letters and only reports ``mixed`` when Latin
    script clearly dominates.
    """
    arabic_letters = len(re.findall(r"[\u0600-\u06FF]", text))
    latin_letters = len(re.findall(r"[A-Za-z]", text))
    if not arabic_letters:
        return "en"
    if not latin_letters:
        return "ar"
    return "mixed" if latin_letters > 6 * arabic_letters else "ar"


def response_language_for_query(message: str) -> str:
    """Select the generation language hint for the model.

    ``mixed`` tells the model to write Arabic sentences and keep English
    medical terms, so an Arabic question naming a drug in Latin script gets
    that hint even though the reply itself is Arabic prose.
    """
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", message))
    has_latin = bool(re.search(r"[A-Za-z]", message))
    # Franco-Arabic is written in Latin but the intended language is Arabic.
    from app.retrieval.franco_normalizer import is_likely_franco

    if is_likely_franco(message):
        return "ar"
    if has_arabic and has_latin:
        return "mixed"
    return "ar" if has_arabic else "en"


def static_reply_language(message: str) -> str:
    """Language of the fixed abstention or escalation reply.

    The API's ``language`` field describes the reply that is actually returned.
    A fixed Arabic escalation message must therefore be labelled ``ar`` even
    when the question names a drug in Latin script ("أديله Ventolin؟").
    """
    from app.retrieval.franco_normalizer import is_likely_franco

    if is_likely_franco(message):
        return "ar"
    return detect_answer_language(message)
