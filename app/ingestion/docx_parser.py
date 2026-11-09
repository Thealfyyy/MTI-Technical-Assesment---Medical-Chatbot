"""Deterministic, heading-, sub-section-, and table-aware DOCX parser for the MTI Medical Chatbot.

Preserves Arabic Unicode, document hierarchy, drug classes, clinical sub-sections,
and embedded data tables (Trade Names, Active Ingredients, OTC status).
Eliminates stub/header-only chunks and ensures atomic preservation of clinical contraindications.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterator

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
import yaml

from app.schemas.chunk import ChunkMetadata, DocumentChunk

# Major topic patterns (Level 1 in document hierarchy)
MAJOR_TOPIC_RE = re.compile(
    r"^(\d+[\.\)]\s+)?("
    r"أدوية الربو|أدوية الانسداد الرئوي|أدوية قرحة المعدة|Nausea & Vomiting|الغثيان والقيء|"
    r"Pain & Fever|الألم والحرارة|Headache & Migraine|الصداع|"
    r"أدوية التهاب الحلق|أدوية الالتهاب الرئوي|أدوية الحساسية|الجيوب الأنفية|"
    r"أدوية السكر|أدوية الضغط|أدوية الكوليسترول|القولون العصبي|التهاب المفاصل"
    r").*",
    re.IGNORECASE,
)

# Numbered drug category patterns (Level 2 in document hierarchy)
CATEGORY_NUM_RE = re.compile(r"^(\d+[\.\)]\s+[A-Za-z0-9\u0600-\u06FF].+|[A-Z][\.\)]\s+[A-Za-z0-9\u0600-\u06FF].+)$")

# Sub-section markers (Level 3 within drug category)
SUBSECTION_KEYWORDS = [
    ("Contraindications", re.compile(r"(contraindication|موانع الاستعمال|تحذيرات|أهم التحذيرات)", re.IGNORECASE)),
    ("Side Effects", re.compile(r"(side effect|الآثار الجانبية|الأعراض الجانبية|adverse effect)", re.IGNORECASE)),
    ("Trade Names", re.compile(r"(السوق المصري|الأسماء التجارية|trade name|brand name|المستحضرات الموجودة)", re.IGNORECASE)),
    ("Indications", re.compile(r"(دواعي الاستعمال|indication|استخدامات|الاستخدام)", re.IGNORECASE)),
    ("OTC Status", re.compile(r"(otc ولا prescription|otc vs prescription|ملخص otc)", re.IGNORECASE)),
    ("Interactions", re.compile(r"(تفاعلات دوائية|interaction|alcohol|كحول)", re.IGNORECASE)),
    ("Dosage", re.compile(r"(الجرعات|تعديل الجرعة|dosage|dosing)", re.IGNORECASE)),
]


def normalize_text_unicode(text: str) -> str:
    """Normalize Unicode and clean excessive whitespace while preserving Arabic characters."""
    normalized = unicodedata.normalize("NFC", text)
    # Remove control characters except standard line breaks
    normalized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", normalized)
    # Collapse non-newline whitespace
    normalized = re.sub(r"[ \t\xa0]+", " ", normalized)
    return normalized.strip()


def identify_subsection(text: str) -> str | None:
    """Check if a line serves as a clinical subsection header."""
    if len(text) > 85:
        return None
    for label, pattern in SUBSECTION_KEYWORDS:
        if pattern.search(text):
            return label
    return None


def iter_block_items(doc: Document) -> Iterator[Paragraph | Table]:
    """Yield all paragraphs and tables in their exact document order."""
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("tbl"):
            yield Table(child, doc)


def format_table_as_lines(table: Table) -> list[str]:
    """Convert a Word table into clean, readable structured text lines."""
    lines: list[str] = []
    rows = table.rows
    if not rows:
        return lines

    headers = [normalize_text_unicode(c.text).replace("\n", " ") for c in rows[0].cells]
    for row in rows[1:]:
        cell_vals = [normalize_text_unicode(c.text).replace("\n", " ") for c in row.cells]
        if not any(cell_vals):
            continue
        parts: list[str] = []
        for i, val in enumerate(cell_vals):
            if not val:
                continue
            hdr = headers[i] if i < len(headers) and headers[i] else f"Field{i+1}"
            parts.append(f"{hdr}: {val}")
        if parts:
            lines.append(" | ".join(parts))
    return lines


def parse_docx_file(file_path: Path, doc_id: str, doc_title: str) -> list[DocumentChunk]:
    """Parse a single DOCX document into deterministic, sub-section- and table-aware chunks."""
    doc = Document(str(file_path))
    chunks: list[DocumentChunk] = []

    current_major = doc_title.split("/")[0].strip()
    current_category = ""
    current_sub = ""
    buffer: list[str] = []

    def flush_chunk() -> None:
        nonlocal buffer
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        buffer = []
        if not body or len(body) < 18:
            return

        # Build clean section breadcrumb
        parts = [current_major]
        if current_category and current_category != current_major:
            parts.append(current_category)
        if current_sub:
            parts.append(current_sub)
        section_path = " > ".join(parts)

        # Discard stubs where body is solely the section header
        if body == current_major or body == current_category or body == current_sub:
            return

        chunk_num = len(chunks) + 1
        chunk_id = f"{doc_id}-C{chunk_num:03d}"
        full_text = f"[{doc_id}] {doc_title} | {section_path}\n{body}"
        snippet = re.sub(r"\s+", " ", body)[:280].strip()

        metadata = ChunkMetadata(
            doc_id=doc_id,
            title=doc_title,
            section=section_path,
            chunk_id=chunk_id,
            snippet=snippet,
            char_count=len(body),
        )

        chunks.append(
            DocumentChunk(
                id=chunk_id,
                text=full_text,
                metadata=metadata,
            )
        )

    for block in iter_block_items(doc):
        if isinstance(block, Table):
            table_lines = format_table_as_lines(block)
            if not table_lines:
                continue
            # If current_sub is empty, default to Trade Names or Table Data
            if not current_sub:
                current_sub = "Trade Names & Formulations"
            buffer.extend(table_lines)
            if sum(len(line) for line in buffer) >= 420:
                flush_chunk()
            continue

        # Otherwise block is a Paragraph
        p = block
        txt = normalize_text_unicode(p.text)
        if not txt:
            continue

        style_name = p.style.name if p.style else "Normal"
        is_bold = any(run.bold for run in p.runs if run.text.strip())
        is_heading_style = "Heading" in style_name or "Title" in style_name

        # Check for Major Topic
        is_major = bool(MAJOR_TOPIC_RE.match(txt)) and len(txt) < 95
        if is_major and (is_heading_style or is_bold or "Normal" in style_name):
            flush_chunk()
            current_major = txt
            current_category = ""
            current_sub = ""
            continue

        # Check for Category / Drug Class
        is_category = bool(CATEGORY_NUM_RE.match(txt)) and len(txt) < 85 and not any(kw[1].search(txt) for kw in SUBSECTION_KEYWORDS)
        if is_category and (is_heading_style or is_bold or style_name in ("Normal", "Normal (Web)")):
            flush_chunk()
            current_category = txt
            current_sub = ""
            continue

        # Check for Subsection (Side Effects, Contraindications, Trade Names, etc.)
        sub_label = identify_subsection(txt)
        if sub_label and (is_heading_style or is_bold or len(txt) < 55 or ":" in txt or "؟" in txt or "?" in txt):
            flush_chunk()
            current_sub = sub_label
            colon_idx = max(txt.find(":"), txt.find("："))
            if colon_idx != -1 and len(txt[colon_idx + 1 :].strip()) > 10:
                buffer.append(txt[colon_idx + 1 :].strip())
            continue

        # Normal body paragraph
        buffer.append(txt)
        if sum(len(line) for line in buffer) >= 420:
            flush_chunk()

    flush_chunk()
    return chunks


def parse_all_manifest_documents(manifest_path: Path, project_root: Path) -> list[DocumentChunk]:
    """Parse all documents listed in kb_manifest.yaml."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    all_chunks: list[DocumentChunk] = []
    for doc in manifest["documents"]:
        doc_path = project_root / doc["relative_path"]
        if not doc_path.exists():
            raise FileNotFoundError(f"Corpus document not found: {doc_path}")
        chunks = parse_docx_file(doc_path, doc["doc_id"], doc["title"])
        all_chunks.extend(chunks)

    return all_chunks
