#!/usr/bin/env python3
"""Multi-strategy text chunking for RAG document ingestion.

Strategy 1: Markdown headers (^#{1,3} followed by text) -- for markdown docs
Strategy 2: Plain-text section label heuristics -- for PDF-extracted text
Fallback: Double-newline splitting with min_chars=200
"""
import re
from typing import List, Dict

# Strategy 1: Markdown headers
MARKDOWN_HEADER_PATTERN = re.compile(r"^#{1,3}\s+.+", re.MULTILINE)

# Strategy 2: Common grant document section labels (case-insensitive)
# These appear in PDF-extracted text as standalone lines
GRANT_SECTION_LABELS = [
    "Program Description", "Project Description", "Need/Problem Statement",
    "Need Statement", "Problem Statement", "Goals and Objectives",
    "Evaluation Plan", "Budget Narrative", "Budget Summary",
    "Organizational Background", "Organization Background",
    "Executive Summary", "Project Summary", "Abstract",
    "Implementation Plan", "Timeline", "Staffing Plan",
    "Statement of Need", "Project Narrative", "Methodology",
    "Sustainability Plan", "Letters of Support", "Appendix",
    "Scope of Work", "Work Plan", "Logic Model",
    "Performance Measures", "Outcomes", "Project Design",
]

# Build regex: match lines that are section labels (preceded by newline, followed by newline or colon)
_label_pattern = "|".join(re.escape(label) for label in GRANT_SECTION_LABELS)
SECTION_LABEL_PATTERN = re.compile(
    rf"^(?:{_label_pattern})\s*:?\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Fallback: double-newline splitting
DOUBLE_NEWLINE_PATTERN = re.compile(r"\n\s*\n")

MIN_CHUNK_LENGTH = 50
FALLBACK_MIN_CHARS = 200


def chunk_by_section(
    text: str,
    source_file: str,
    doc_type: str,
    funder: str = "",
    year: str = "",
) -> List[Dict]:
    """Split text into chunks using multi-strategy approach.

    1. Try markdown headers first (for .md files)
    2. Try plain-text section labels (for PDF-extracted text)
    3. Fallback to double-newline splitting if fewer than 3 sections found
    """
    # Strategy 1: Markdown headers
    chunks = _split_by_pattern(text, MARKDOWN_HEADER_PATTERN, source_file, doc_type, funder, year)
    if len(chunks) >= 3:
        return chunks

    # Strategy 2: Plain-text section labels
    chunks = _split_by_pattern(text, SECTION_LABEL_PATTERN, source_file, doc_type, funder, year)
    if len(chunks) >= 3:
        return chunks

    # Fallback: double-newline splitting
    return _split_by_double_newline(text, source_file, doc_type, funder, year)


def _split_by_pattern(
    text: str,
    pattern: re.Pattern,
    source_file: str,
    doc_type: str,
    funder: str,
    year: str,
) -> List[Dict]:
    """Split text using a regex pattern as section delimiter."""
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    chunks = []
    # Content before first match
    pre_content = text[:matches[0].start()].strip()
    if len(pre_content) >= MIN_CHUNK_LENGTH:
        chunks.append(_make_chunk(pre_content, "Introduction", source_file, doc_type, funder, year, 0))

    # Content between matches
    for i, match in enumerate(matches):
        header = match.group().strip().lstrip("#").strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if len(content) >= MIN_CHUNK_LENGTH:
            chunks.append(_make_chunk(content, header, source_file, doc_type, funder, year, len(chunks)))

    return chunks


def _split_by_double_newline(
    text: str,
    source_file: str,
    doc_type: str,
    funder: str,
    year: str,
) -> List[Dict]:
    """Fallback: split on double newlines, merge small chunks."""
    parts = DOUBLE_NEWLINE_PATTERN.split(text)
    chunks = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        current = f"{current}\n\n{part}" if current else part
        if len(current) >= FALLBACK_MIN_CHARS:
            chunks.append(_make_chunk(current, f"Section {len(chunks) + 1}", source_file, doc_type, funder, year, len(chunks)))
            current = ""
    if current and len(current) >= MIN_CHUNK_LENGTH:
        chunks.append(_make_chunk(current, f"Section {len(chunks) + 1}", source_file, doc_type, funder, year, len(chunks)))
    return chunks


def _make_chunk(
    content: str,
    section_title: str,
    source_file: str,
    doc_type: str,
    funder: str,
    year: str,
    chunk_index: int,
) -> Dict:
    return {
        "content": content,
        "section_title": section_title,
        "source_file": source_file,
        "doc_type": doc_type,
        "funder": funder,
        "year": year,
        "chunk_index": chunk_index,
    }
