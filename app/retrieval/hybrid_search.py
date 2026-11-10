"""Hybrid Retrieval Engine combining BAAI/bge-m3 Dense Search and BM25/Lexical Search.

Uses Reciprocal Rank Fusion (RRF) to merge dense semantic similarity with
exact-match lexical signals for trade names, drug classes, and clinical keywords.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

from app.retrieval.franco_normalizer import (
    extract_keywords_for_lexical_search,
    is_likely_franco,
    normalize_franco_to_arabic,
)
from app.schemas.chunk import DocumentChunk, RetrievedChunk

logger = logging.getLogger(__name__)


BILINGUAL_SYNONYMS: dict[str, list[str]] = {
    # Common cross-lingual clinical concepts
    "alcohol": ["كحول", "الكحول"],
    "كحول": ["alcohol"],
    "active": ["فعالة", "المادة"],
    "ingredient": ["المادة", "الفعالة"],
    "contraindication": ["موانع", "الاستعمال", "تحذيرات"],
    "contraindications": ["موانع", "الاستعمال", "تحذيرات"],
    "موانع": ["contraindications", "contraindication"],
    "ممنوع": ["contraindications", "contraindication", "موانع"],
    "side": ["آثار", "جانبية", "أعراض"],
    "effects": ["جانبية", "الآثار", "الأعراض"],
    "آثار": ["side", "effects"],
    "جانبية": ["side", "effects"],
    "أعراض": ["symptoms", "side", "effects"],
    "بدائل": ["alternatives", "alternative", "substitute"],
    "بديل": ["alternative", "alternatives"],
    "alternative": ["بدائل", "بديل"],
    "alternatives": ["بدائل", "بديل"],
    # Drug class, brand, and active ingredient cross-lingual mappings
    "salbutamol": ["saba", "ventolin", "فنتولين", "سالبوتامول"],
    "سالبوتامول": ["salbutamol", "ventolin", "فنتولين"],
    "ventolin": ["salbutamol", "saba", "فنتولين"],
    "فنتولين": ["ventolin", "salbutamol", "سالبوتامول"],
    "saba": ["salbutamol", "ventolin"],
    "laba": ["salmeterol", "formoterol"],
    "arbs": ["angiotensin", "losartan", "valsartan", "أنجيوتنسين"],
    "أنجيوتنسين": ["arbs", "angiotensin", "losartan"],
    "nsaids": ["ibuprofen", "diclofenac", "cataflam", "brufen"],
    "brufen": ["ibuprofen", "بروفين", "nurofen", "profinal"],
    "بروفين": ["brufen", "ibuprofen", "cataflam"],
    "cataflam": ["diclofenac", "potassium", "كاتافلام"],
    "كاتافلام": ["cataflam", "diclofenac"],
    "paracetamol": ["panadol", "cetal", "paramol", "باراسيتامول", "بنادول"],
    "باراسيتامول": ["paracetamol", "panadol", "cetal", "paramol"],
    "panadol": ["paracetamol", "باراسيتامول", "بنادول"],
    "بنادول": ["panadol", "paracetamol"],
    "metronidazole": ["flagyl", "فلاجيل", "كحول", "alcohol", "ميترونيدازول"],
    "ميترونيدازول": ["metronidazole", "flagyl", "فلاجيل"],
    "فلاجيل": ["flagyl", "metronidazole"],
    "metformin": ["ميتفورمين", "biguanides", "glucophage", "جلوكوفاج", "cidophage", "سيدوفاج"],
    "ميتفورمين": ["metformin", "biguanides", "glucophage", "جلوكوفاج", "cidophage", "سيدوفاج"],
    "biguanides": ["metformin", "ميتفورمين", "glucophage"],
    "glucophage": ["metformin", "ميتفورمين", "biguanides"],
    "جلوكوفاج": ["glucophage", "metformin", "ميتفورمين"],
    "ezetimibe": ["إزيتيميب", "ezetrol", "cholesterol", "كوليسترول"],
    "إزيتيميب": ["ezetimibe", "ezetrol", "cholesterol", "كوليسترول"],
    "duspatalin": ["دوسباتالين", "mebeverine", "ميبفرين", "قولون", "spasm"],
    "دوسباتالين": ["duspatalin", "mebeverine", "ميبفرين", "قولون"],
    "mebeverine": ["duspatalin", "دوسباتالين", "ميبفرين"],
    "clarithromycin": ["كلاريثرومايسين", "klacid", "كلاسيد", "macrolide"],
    "كلاريثرومايسين": ["clarithromycin", "klacid", "كلاسيد"],
    "sglt2": ["forxiga", "فورسيجا", "dapagliflozin", "jardiance", "جارديانس", "gliflozins"],
    "forxiga": ["sglt2", "dapagliflozin", "فورسيجا"],
    "فورسيجا": ["forxiga", "sglt2", "dapagliflozin"],
    "oseltamivir": ["tamiflu", "تاميفلو", "أوسيلتاميفير"],
    "تاميفلو": ["tamiflu", "oseltamivir"],
    "bismuth": ["بزموت", "بيسموث", "pepto"],
    "بزموت": ["bismuth", "بيسموث"],
    "mycophenolate": ["ميكوفينولات", "cellcept", "سيلسيبت"],
    "ميكوفينولات": ["mycophenolate", "cellcept", "سيلسيبت"],
    "saline": ["محلول", "ملحي", "بخاخ", "شطف"],
    "omeprazole": ["أوميبرازول", "losec", "حموضة", "قرحة", "gerd"],
    "أوميبرازول": ["omeprazole", "losec", "حموضة"],
    # Nouns the Franco normalizer emits. The corpus writes these with the
    # definite article ("القولون", "الأعراض") or in English, so a bare Arabic
    # noun from a Franco query needs the corpus form to score lexically.
    "مادة": ["المادة", "active", "ingredient"],
    "فعالة": ["الفعالة", "active", "ingredient"],
    "اسم": ["name", "الاسم", "trade"],
    "تجارية": ["trade", "brand", "التجارية"],
    "قولون": ["القولون", "colon", "ibs"],
    "حموضة": ["الحموضة", "acidity", "heartburn", "gerd"],
    "أعراض": ["الأعراض", "side", "effects"],
    "جرعة": ["الجرعة", "dose", "dosing"],
    "معدة": ["المعدة", "stomach", "gastric", "ulcer"],
    "صداع": ["الصداع", "headache", "migraine"],
    "سخونة": ["السخونة", "fever", "temperature"],
    "حساسية": ["الحساسية", "allergy", "allergic", "histamine"],
    "ربو": ["الربو", "asthma"],
    "سكر": ["السكر", "diabetes", "glucose", "diabetic"],
    "ضغط": ["الضغط", "hypertension", "blood", "pressure"],
    "إسهال": ["diarrhea", "الإسهال"],
    "قيء": ["vomiting", "القيء", "nausea"],
    "كحة": ["cough", "الكحة"],
    "حلق": ["throat", "الحلق", "pharyngitis"],
    "ألم": ["pain", "الألم"],
    "وجع": ["pain", "الألم"],
    "شفايف": ["lips", "الشفايف"],
    "زرقا": ["blue", "زرقاء"],
    "نفس": ["breathing", "breath", "التنفس"],
    "استعمال": ["use", "استخدام", "indication"],
    "يستخدم": ["used", "use", "indication"],
}

# Arabic transliterations of trade names -> the exact Latin spelling the corpus
# uses. Pharmacists type "بروفين" while the knowledge base writes "Brufen";
# without this bridge the Arabic-script query falls below the dense abstention
# threshold (0.468 measured) and the trade-name table can never be reached.
# This is a lexical alias table only: it names drugs that already exist in the
# corpus and never states what any of them does.
CORPUS_NAME_ALIASES: dict[str, str] = {
    "بروفين": "Brufen",
    "نوروفين": "Nurofen",
    "بروفينال": "Profinal",
    "ايبوفلام": "Ibuflam",
    "كاتافلام": "Cataflam",
    "فولتارين": "Voltaren",
    "موبيك": "Mobic",
    "سيليبريكس": "Celebrex",
    "اركوكسيا": "Arcoxia",
    "نابروسين": "Naprosyn",
    "فيلدين": "Feldene",
    "بانادول": "Panadol",
    "بنادول": "Panadol",
    "سيتال": "Cetal",
    "ادول": "Adol",
    "بارامول": "Paramol",
    "فيفادول": "Fevadol",
    "ابيمول": "Abimol",
    "كالوبول": "Calpol",
    "اوجمنتين": "Augmentin",
    "اموكسيل": "Amoxil",
    "كلاسيد": "Klacid",
    "لوزيك": "Losec",
    "اوميز": "Omez",
    "نيكسيوم": "Nexium",
    "كونترولوك": "Controloc",
    "بانتولوك": "Pantoloc",
    "بوسكوبان": "Buscopan",
    "ايفيرالجان": "Efferalgan",
    "دوسباتالين": "Duspatalin",
    "فنتولين": "Ventolin",
    "جلوكوفاج": "Glucophage",
    "فلاجيل": "Flagyl",
    "تاميفلو": "Tamiflu",
    "فورسيجا": "Forxiga",
    "جارديانس": "Jardiance",
    "ايزيترول": "Ezetrol",
    "كونكور": "Concor",
    "ميتفورمين": "Metformin",
    "تيوتروبيوم": "Tiotropium",
    "سبيريفا": "Spiriva",
    "مونتيلوكاست": "Montelukast",
    "ميتوكلوبراميد": "Metoclopramide",
    "سيمفاستاتين": "Simvastatin",
    "ميثوتريكسات": "Methotrexate",
    "كلاريثرومايسين": "Clarithromycin",
    "اموكسيسيلين": "Amoxicillin",
    "بنسلين": "Penicillin",
}

# Arabic punctuation (including ؟ U+061F) lives inside the \u0600-\u06FF block,
# so a naive run glues it to the word: "بروفين؟" would never match "بروفين".
_ARABIC_RUN = re.compile(r"[\u0600-\u06FF]+")
_ARABIC_EDGE_PUNCTUATION = "\u060c\u061b\u061f\u066a\u066b\u066c\u066d\u06d4"


def expand_corpus_aliases(query: str) -> str:
    """Append the corpus spelling of any Arabic trade-name transliteration.

    The original wording is preserved; the Latin name is added so that both the
    embedding and the BM25 query carry the spelling the corpus actually uses.
    """
    found: list[str] = []
    for raw in _ARABIC_RUN.findall(query):
        token = raw.strip(_ARABIC_EDGE_PUNCTUATION)
        candidates = [token]
        if token.startswith("ال") and len(token) > 4:
            candidates.append(token[2:])
        for candidate in candidates:
            latin = CORPUS_NAME_ALIASES.get(candidate)
            if latin:
                found.append(latin)
    if not found:
        return query
    return f"{query} {' '.join(dict.fromkeys(found))}"


# Arabic punctuation sits inside the \u0600-\u06FF block, so a naive token pattern
# glues it to the preceding word: "Controloc؟" tokenizes as one token and can
# never match the corpus brand name. Strip it, plus the diacritics that would
# otherwise make a vocalized word a different token from its unvocalized form.
_ARABIC_PUNCTUATION = "\u060c\u061b\u061f\u066a\u066b\u066c\u066d\u06d4"
_ARABIC_DIACRITICS = re.compile("[\u064b-\u0652\u0670\u0640]")

BM25_STOP_WORDS: set[str] = {
    "what", "are", "the", "of", "in", "is", "for", "with", "to", "a", "an", "do", "does", "any",
    "there", "patient", "should", "know", "about", "common", "how", "can", "when", "why", "where",
    "ما", "هي", "هو", "في", "من", "عن", "مع", "هل", "ايه", "إيه", "ده", "دي", "عايز", "اعرف", "لو", "او", "أو",
    "ينفع", "ممكن", "عندي", "بتاعة", "بتاع", "ودكتور", "دكتور", "كتبلي", "ليها", "زي",
    "على", "إلى", "ال", "إزاي", "امتى", "فين", "ليه",
}


class SimpleBM25Index:
    """In-memory BM25 index built directly from parsed DocumentChunks."""

    def __init__(self, chunks: list[DocumentChunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks = {c.id: c for c in chunks}
        self.doc_ids = [c.id for c in chunks]
        self.corpus_size = len(chunks)

        # Tokenize corpus
        self.doc_lengths: dict[str, int] = {}
        self.doc_freqs: dict[str, int] = Counter()
        self.term_freqs: dict[str, Counter[str]] = {}

        total_length = 0
        for chunk in chunks:
            # Index both the breadcrumbs and body text
            tokens = self._tokenize(chunk.text)
            self.doc_lengths[chunk.id] = len(tokens)
            total_length += len(tokens)
            tf = Counter(tokens)
            self.term_freqs[chunk.id] = tf
            for term in tf:
                self.doc_freqs[term] += 1

        self.avg_doc_length = total_length / max(1, self.corpus_size)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # Match Arabic and Latin alphanumeric tokens, then trim the Arabic
        # punctuation the character class unavoidably includes at the edges.
        cleaned = _ARABIC_DIACRITICS.sub("", text.lower())
        tokens = re.findall(r"[\u0600-\u06FFa-zA-Z0-9]+", cleaned)
        return [t for t in (token.strip(_ARABIC_PUNCTUATION) for token in tokens) if len(t) > 1]

    def idf(self, term: str) -> float:
        n = self.doc_freqs.get(term, 0)
        return math.log(1.0 + (self.corpus_size - n + 0.5) / (n + 0.5))

    def exact_term_matches(
        self, query: str, max_doc_freq: int = 8, top_k: int = 3
    ) -> list[RetrievedChunk]:
        """Return chunks containing a distinctive, capitalized Latin query term.

        Dense similarity often misses a single brand name buried in a long
        trade-name table. Trade names are written with an initial capital in the
        corpus (``Controloc``) while ordinary English words in running text are
        not, so a rare *and* capitalized Latin token is treated as an exact drug
        or brand lookup. Without this, a query such as ``active ingredient in
        Controloc`` can be answered from an unrelated passage that merely shares
        the words "active ingredient".
        """
        rare_tokens = [
            token
            for token in dict.fromkeys(self._tokenize(query))
            if len(token) >= 4
            and token.isascii()
            and 0 < self.doc_freqs.get(token, 0) <= max_doc_freq
        ]
        if not rare_tokens:
            return []

        scored: list[tuple[str, float]] = []
        for chunk_id in self.doc_ids:
            text = self.chunks[chunk_id].text
            matched = [
                token
                for token in rare_tokens
                if any(
                    occ[:1].isupper()
                    for occ in re.findall(
                        rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", text, re.IGNORECASE
                    )
                )
            ]
            if matched:
                scored.append((chunk_id, float(sum(self.idf(token) for token in matched))))

        scored.sort(key=lambda item: item[1], reverse=True)
        results: list[RetrievedChunk] = []
        for rank, (chunk_id, score) in enumerate(scored[:top_k], start=1):
            chunk = self.chunks[chunk_id]
            results.append(
                RetrievedChunk(
                    doc_id=chunk.metadata.doc_id,
                    title=chunk.metadata.title,
                    section=chunk.metadata.section,
                    chunk_id=chunk.id,
                    snippet=chunk.metadata.snippet,
                    text=chunk.text,
                    score=score,
                    rank=rank,
                    source="lexical-exact",
                )
            )
        return results

    def search(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        """Score all chunks against query tokens using standard BM25 formula."""
        raw_tokens = self._tokenize(query)
        if not raw_tokens:
            return []

        # Filter out conversational stop words to boost clinical keyword signal
        filtered_tokens = [t for t in raw_tokens if t not in BM25_STOP_WORDS]
        base_tokens = filtered_tokens if filtered_tokens else raw_tokens

        # Expand query tokens with bilingual synonyms
        expanded_tokens: list[str] = list(base_tokens)
        for token in base_tokens:
            if token in BILINGUAL_SYNONYMS:
                expanded_tokens.extend(BILINGUAL_SYNONYMS[token])

        tokens = list(dict.fromkeys(expanded_tokens))

        scores: list[tuple[str, float]] = []
        for chunk_id in self.doc_ids:
            doc_len = self.doc_lengths[chunk_id]
            tf_dict = self.term_freqs[chunk_id]
            score = 0.0

            for term in tokens:
                if term not in tf_dict:
                    continue
                tf = tf_dict[term]
                idf = self.idf(term)
                # BM25 term weighting
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(1.0, self.avg_doc_length)))
                score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append((chunk_id, score))

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)

        results: list[RetrievedChunk] = []
        for rank, (chunk_id, score) in enumerate(scores[:top_k], start=1):
            chunk = self.chunks[chunk_id]
            results.append(
                RetrievedChunk(
                    doc_id=chunk.metadata.doc_id,
                    title=chunk.metadata.title,
                    section=chunk.metadata.section,
                    chunk_id=chunk.id,
                    snippet=chunk.metadata.snippet,
                    text=chunk.text,
                    score=float(score),
                    rank=rank,
                    source="lexical",
                )
            )

        return results


def reciprocal_rank_fusion(
    dense_results: list[RetrievedChunk],
    lexical_results: list[RetrievedChunk],
    top_k: int = 3,
    rrf_k: int = 60,
    dense_weight: float = 0.65,
    lexical_weight: float = 0.35,
) -> list[RetrievedChunk]:
    """Fuse dense and lexical search results using Reciprocal Rank Fusion (RRF)."""
    scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(dense_results, start=1):
        chunk_map[chunk.chunk_id] = chunk
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + dense_weight / (rrf_k + rank)

    for rank, chunk in enumerate(lexical_results, start=1):
        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + lexical_weight / (rrf_k + rank)

    # Sort descending by fused RRF score
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused_results: list[RetrievedChunk] = []
    for rank, cid in enumerate(sorted_ids[:top_k], start=1):
        original = chunk_map[cid]
        fused_chunk = RetrievedChunk(
            doc_id=original.doc_id,
            title=original.title,
            section=original.section,
            chunk_id=original.chunk_id,
            snippet=original.snippet,
            text=original.text,
            score=scores[cid],
            rank=rank,
            source="hybrid",
        )
        fused_results.append(fused_chunk)

    return fused_results
