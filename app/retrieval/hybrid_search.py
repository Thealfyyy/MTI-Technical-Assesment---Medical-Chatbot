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
}


BM25_STOP_WORDS: set[str] = {
    "what", "are", "the", "of", "in", "is", "for", "with", "to", "a", "an", "do", "does", "any",
    "there", "patient", "should", "know", "about", "common", "how", "can", "when", "why", "where",
    "ما", "هي", "هو", "في", "من", "عن", "مع", "هل", "ايه", "ده", "دي", "عايز", "اعرف", "لو", "او", "أو",
    "ينفع", "ممكن", "عندي", "بتاعة", "بتاع", "ودكتور", "دكتور", "كتبلي", "ليها", "زي",
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
        # Match Arabic and Latin alphanumeric tokens
        tokens = re.findall(r"[\u0600-\u06FFa-zA-Z0-9]+", text.lower())
        return [t for t in tokens if len(t) > 1]

    def idf(self, term: str) -> float:
        n = self.doc_freqs.get(term, 0)
        return math.log(1.0 + (self.corpus_size - n + 0.5) / (n + 0.5))

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
