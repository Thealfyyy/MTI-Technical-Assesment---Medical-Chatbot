"""Egyptian Dialect and Franco-Arabic (Arabizi) Normalizer.

Franco-Arabic (Arabizi) has no standard orthography: the same word is written
differently by different people, and one Egyptian word has been recorded with
more than twenty spellings in the BOLT Egyptian SMS/chat corpus. Two
consequences shape this module:

* Every supported spelling is an explicit key. There is deliberately **no**
  fuzzy matching: in a pharmacy context a wrong match is worse than no match.
* A token that is not recognised is returned **unchanged**. The previous
  implementation transliterated the digits of unknown tokens and left the
  Latin letters in place, so ``fa3ala`` became ``فعala`` - a mixed-script token
  that matches neither the Arabic corpus nor the Latin drug names.

Lookup applies light, deterministic normalisation only (case, punctuation
including the Arabic question mark, hyphens, repeated-letter elongation, and
the digit/letter equivalences 7~h, 5~kh, 9~s, 6~t). Pure numbers are never
transliterated, so a dose such as ``500 mg`` stays intact.

Digitiser mappings follow the conventional Egyptian set (2 = hamza/ء,
3 = ع, 5 = خ, 6 = ط, 7 = ح, 9 = ص).
"""

from __future__ import annotations

import re

# Common Franco-Arabic character map. Kept as the documented digit alphabet;
# transliteration itself happens through FRANCO_LEXICON entries, never by
# rewriting the digits of an arbitrary token.
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

# Lexicon of high-frequency Egyptian Franco spelling variants, grouped by the
# Arabic headword they mean. Headwords carry no definite article so that the
# "el-/fel-" prefixes can be resolved generically.
FRANCO_LEXICON: dict[str, tuple[str, ...]] = {
    # --- symptoms and conditions -------------------------------------------
    "حموضة": ("7omoda", "7omouda", "7omooda", "7omodah", "7omoudah", "7mouda",
              "homoda", "homouda", "7omo2a", "homo2a", "7mo2a"),
    "حرقان": ("7or2an", "7orqan", "hor2an", "7ar2an"),
    "صداع": ("soda3", "sodaa3", "soda3a", "sod3", "suda3", "sudaa3"),
    "مغص": ("maghs", "maghes", "maghss", "mags"),
    "سخونة": ("so5ona", "so5oona", "sokhona", "so5onah", "sokhona"),
    "ترجيع": ("tergee3", "targee3", "targi3", "terge3"),
    "قيء": ("qay2", "2ay2", "2aye2", "qaye2", "2ay2a"),
    "إسهال": ("eshal", "ishal", "esehal", "ishaal", "eshaal"),
    "ربو": ("rebo", "rabo", "ribo", "rabw"),
    "حساسية": ("hasaseya", "7asaseya", "7asasya", "hasasya"),
    "قولون": ("2olon", "2oloon", "qoloon", "qolon", "colon"),
    "سكر": ("sokar", "sokkar", "sukkar", "sokr"),
    "ضغط": ("daght", "da8t", "dagt", "daghet"),
    "كوليسترول": ("koleystrol", "kolestrol", "kolesterol", "cholesterol"),
    "وجع": ("waga3", "waja3", "wag3", "waga3a"),
    "ألم": ("alam", "2alam", "allam"),
    "التهاب": ("eltahab", "eltehab", "elt7ab"),
    "زور": ("zour", "zor", "zoor"),
    "حلق": ("halq", "7al2", "7alg", "hal2"),
    "معدة": ("ma3eda", "ma3da", "ma3edah", "m3eda"),
    "كحة": ("ka7a", "k7a", "kohha", "k7ha"),
    "دوخة": ("dokha", "do5a", "dawkha"),
    "رجفة": ("regfa", "ragfa", "reghfa"),
    "خفقان": ("khaf2an", "5af2an", "khafqan"),
    "برد": ("bard", "barad"),
    "نفس": ("nafas", "nafs"),
    "ضيق": ("zay2", "day2", "dai2", "daye2", "zaye2"),
    "شفايف": ("shafaif", "shafayef", "shafayf", "shefaif", "shafaifo", "shafayfo"),
    "أديله": ("adilo", "adeelo", "adelo"),
    "زرقا": ("zar2a", "zarga", "zarqa", "zar2aa"),
    "عيان": ("3ayan", "3ayyan"),
    "شديد": ("shadeed", "shadid"),
    # --- pharmacy and question words ---------------------------------------
    "إيه": ("eh", "eih", "aih", "2eh", "ehh"),
    "إزاي": ("ezay", "ezzay", "2ezay"),
    "ليه": ("leeh", "leh", "leih", "le"),
    "مع": ("ma3", "m3a", "ma3a", "m3"),
    "امتى": ("emta", "imta", "emata", "2emta"),
    "كام": ("kam",),
    "فين": ("feen", "fin"),
    "عايز": ("3ayz", "3ayez", "3awz", "3awez"),
    "أعرف": ("a3raf", "a3rf"),
    "عشان": ("3ashan", "3ashn", "3shan", "ashan"),
    "ينفع": ("yenfa3", "ynfa3", "yinfa3", "yenfa3"),
    "ماينفعش": ("mayenfa3sh", "mynfa3sh", "maynf3sh", "mabenfa3sh"),
    "مفيش": ("mafeesh", "mafish", "mafysh"),
    "ممنوع": ("mamno3", "mamnou3", "mamnu3", "mamnoo3"),
    "ممكن": ("momken", "mumken", "momkn", "mumkin"),
    "عندي": ("3andi", "3andy", "andi"),
    "عنده": ("3ando", "3andoh", "ando"),
    "عندها": ("3andaha", "3andha"),
    "دكتور": ("doktor", "doctoor", "dktor"),
    "دواء": ("dawa", "dawa2", "dawaa"),
    "علاج": ("3elag", "3ilag", "elag"),
    "جرعة": ("gor3a", "gar3a", "gor3ah", "gor3aa", "gur3a", "jor3a"),
    "أقراص": ("agras", "a2ras", "agraas", "2oras"),
    "كبسولة": ("kapsola", "kapsula", "capsola", "kabsola"),
    "فوار": ("fowar", "fawar", "fawwar"),
    "حبوب": ("7abob", "7aboub", "habob"),
    "شراب": ("sharab", "sharaab"),
    "بخاخ": ("bo5a5", "bokhakh", "bo5akh"),
    "لبوس": ("labos", "laboos"),
    "مادة": ("mada", "madda", "madah"),
    "فعالة": ("fa3ala", "fa3la", "fa33ala", "fa3aala", "fa3alah"),
    "بدائل": ("badayel", "badayl", "bdayel", "badayil"),
    "بديل": ("badeel", "badil"),
    "تجارية": ("tegareya", "tegarya", "togareya", "tigareya"),
    "أعراض": ("a3rad", "a3raad"),
    "جانبية": ("ganbia", "ganbeya", "ganbiya", "janbia"),
    "موانع": ("mawane3", "mwane3", "mawaneh", "mwana3", "mawani3"),
    "استعمال": ("est3mal", "este3mal", "est3maal", "ast3mal", "ist3mal"),
    "يستخدم": ("byst5dm", "bystkhdm", "byst5dmo", "yest5dm", "yst5dm",
                "byst3ml", "byst3mel", "yst3ml"),
    "اسم": ("esm", "ism", "esma"),
    # --- brand names Egyptians write in Arabizi (mapped to the Arabic form,
    #     which the retrieval alias table then bridges to the corpus spelling)
    "بروفين": ("brofen", "borofen", "brofin"),
    "كونترولوك": ("kontrolok", "kontroloc", "konterolok"),
    "كاتافلام": ("kataflam", "kataflm"),
    "فولتارين": ("voltarin", "foltarin"),
    "بنادول": ("banadol", "panadool"),
    "دوسباتالين": ("dospatalin", "despatalin"),
    "فنتولين": ("fantolin",),
}

# Connector particles are translated to their Arabic preposition; the following
# token keeps its own translation ("fel 2olon" -> "في القولون").
_CONNECTORS: dict[str, str] = {
    "fel": "في",
    "fil": "في",
    "fl": "في",
    "fi": "في",
    "fe": "في",
    "f": "في",
    "bel": "ب",
    "bil": "ب",
    "lel": "ل",
    "lil": "ل",
    "ll": "ل",
}
_ARTICLES: frozenset[str] = frozenset({"el", "al", "il", "l"})
# Longest first so that "fel"/"lel" win over their "l"/"f" tails.
_PREFIXES: tuple[str, ...] = (
    "fel", "fil", "bel", "bil", "lel", "lil", "fl", "ll", "el", "al", "il", "l",
)

_STRIP_CHARS = ".,?!:;\"'()[]{}/\\|_–—،؛؟«»…"
_SEPARATORS = re.compile(r"[-'’_]+")
_ELONGATION = re.compile(r"(.)\1+")
_DIGIT_EQUIVALENTS = (("7", "h"), ("5", "kh"), ("9", "s"), ("6", "t"))
_FRANCO_DIGIT_PATTERN = re.compile(r"[a-z]+[235789][a-z]+|[235789][a-z]{2,}")
_LATIN_WORD = re.compile(r"[a-z0-9'’]+")


def lookup_key(token: str) -> str:
    """Canonical lookup key for a candidate Franco token.

    Applies only transformations that are safe for a small, curated medical
    vocabulary: casefold, drop punctuation/quotes/hyphens, collapse
    repeated-letter elongation ("7omooda" -> "7omoda"), and fold the
    consonant digit spellings 7/5/9/6 onto their Latin equivalents so
    "7omoda" and "homoda" share a key.
    """
    key = token.casefold().strip(_STRIP_CHARS)
    key = _SEPARATORS.sub("", key)
    key = _ELONGATION.sub(r"\1", key)
    for digit, letters in _DIGIT_EQUIVALENTS:
        key = key.replace(digit, letters)
    return key


def _build_vocab() -> tuple[dict[str, str], dict[str, str], tuple[str, ...]]:
    """Flatten the lexicon into spelling->Arabic and key->Arabic maps."""
    vocab: dict[str, str] = {}
    index: dict[str, str] = {}
    conflicts: list[str] = []
    for arabic, spellings in FRANCO_LEXICON.items():
        for spelling in spellings:
            vocab[spelling] = arabic
            key = lookup_key(spelling)
            previous = index.get(key)
            if previous is not None and previous != arabic:
                conflicts.append(f"{key}: {previous} / {arabic}")
                continue
            index[key] = arabic
    return vocab, index, tuple(conflicts)


# Spelling -> Arabic headword (kept as a flat mapping for callers/tests).
FRANCO_VOCAB_MAP, _FRANCO_INDEX, FRANCO_KEY_CONFLICTS = _build_vocab()


def _translate_key(key: str) -> tuple[str, str | None] | None:
    """Resolve a normalised token to Arabic, honouring article/preposition prefixes.

    Returns ``(arabic, connector)``; ``connector`` is set when the token carried
    a preposition (``fel``/``bel``/...) that the Arabic text must keep.
    """
    if key in _FRANCO_INDEX:
        return _FRANCO_INDEX[key], None
    for prefix in _PREFIXES:
        if len(key) <= len(prefix) + 1 or not key.startswith(prefix):
            continue
        arabic = _FRANCO_INDEX.get(key[len(prefix):])
        if arabic is None:
            continue
        # "fel"/"bel"/"lel" are contracted with the article (في ال, بـ ال, لـ ال),
        # so the resolved noun takes the definite form: "fel-2olon" -> "في القولون".
        if arabic.startswith("ال"):
            definite = arabic
        else:
            definite = "ال" + arabic
        if prefix in _ARTICLES:
            return definite, None
        return definite, _CONNECTORS[prefix]
    return None


def is_likely_franco(text: str) -> bool:
    """Detect Franco-Arabic input from digit spellings or known Franco words.

    A single Latin word containing a Franco digit (``so5ona``, ``3ayez``) is
    enough, as are two or more dictionary words. A bare number (``500 mg``) or a
    product code (``D3``) is not: the digit has to sit inside a word.
    """
    lowered = text.casefold()
    words = _LATIN_WORD.findall(lowered)
    if not words:
        return False
    known = [word for word in words if lookup_key(word) in _FRANCO_INDEX]
    if len(known) >= 2:
        return True
    if known and any(ch.isdigit() for ch in known[0]):
        return True
    # "badayel el brufen" carries a single dictionary word but an unmistakable
    # Egyptian particle; English prose almost never contains a bare "el" or "fel".
    if known and any(word in _ARTICLES or word in _CONNECTORS for word in words):
        return True
    return bool(_FRANCO_DIGIT_PATTERN.search(lowered))


def normalize_franco_to_arabic(query: str) -> str:
    """Expand recognised Franco-Arabic tokens to Arabic, preserving everything else.

    Unknown tokens come back exactly as the user wrote them. That is deliberate:
    the corpus is written in Arabic and Latin, so a half-converted token
    (``fa3ala`` -> ``فعala``) matches nothing at all.
    """
    if not query or not is_likely_franco(query):
        return query

    translated: list[str] = []
    pending_article = False
    for token in query.split():
        bare = token.strip(_STRIP_CHARS).casefold()
        if bare in _ARTICLES:
            # A stand-alone article belongs to the next noun ("el mada" ->
            # "المادة"); dropping it would lose the corpus's definite form.
            pending_article = True
            continue
        if bare in _CONNECTORS:
            translated.append(_CONNECTORS[bare])
            # The Egyptian connector already contains the article, so a
            # recognised noun after it takes the definite form: "fel 2olon"
            # -> "في القولون". Brand names pass through untouched.
            pending_article = True
            continue

        resolved = _translate_key(lookup_key(token))
        if resolved is None:
            translated.append(token)
            pending_article = False
            continue

        arabic, connector = resolved
        if connector:
            translated.append(connector)
        if pending_article and not arabic.startswith("ال"):
            arabic = "ال" + arabic
        pending_article = False
        translated.append(arabic)

    return " ".join(translated)


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
