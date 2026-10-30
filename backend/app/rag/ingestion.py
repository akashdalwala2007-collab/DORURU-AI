"""
backend/app/rag/ingestion.py - Document Ingestion & Chunking Engine for DORURU

Features:
- Supports Markdown (.md), Plain Text (.txt), and PDF (.pdf).
- Extracts text while strictly preserving metadata: source filename, section/page, last-updated date.
- Boundary-aware chunking respecting sentence and paragraph boundaries.
"""

import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

class DocumentChunk:
    def __init__(self,
                 chunk_id: str,
                 text: str,
                 source_file: str,
                 doc_type: str,
                 section_title: str,
                 page_number: int,
                 last_modified: str,
                 char_count: int):
        self.chunk_id = chunk_id
        self.text = text
        self.source_file = source_file
        self.doc_type = doc_type
        self.section_title = section_title
        self.page_number = page_number
        self.last_modified = last_modified
        self.char_count = char_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source_file": self.source_file,
            "doc_type": self.doc_type,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "last_modified": self.last_modified,
            "char_count": self.char_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        return cls(
            chunk_id=data["chunk_id"],
            text=data["text"],
            source_file=data["source_file"],
            doc_type=data["doc_type"],
            section_title=data["section_title"],
            page_number=data["page_number"],
            last_modified=data["last_modified"],
            char_count=data["char_count"]
        )

def get_file_last_modified_iso(path: Path) -> str:
    """Returns ISO 8601 formatted last modification timestamp."""
    mtime = path.stat().st_mtime
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def split_text_into_chunks(text: str,
                           chunk_size: int = 500,
                           chunk_overlap: int = 80) -> List[str]:
    """
    Boundary-aware text splitter that splits at paragraph or sentence boundaries.
    """
    clean_text = text.strip()
    if not clean_text:
        return []
    if len(clean_text) <= chunk_size:
        return [clean_text]

    chunks = []
    start = 0
    text_len = len(clean_text)

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunks.append(clean_text[start:].strip())
            break

        # Attempt to split at paragraph boundary first
        split_pos = clean_text.rfind("\n\n", start, end)
        if split_pos == -1 or split_pos <= start + 50:
            # Attempt to split at newline
            split_pos = clean_text.rfind("\n", start, end)
        if split_pos == -1 or split_pos <= start + 50:
            # Attempt to split at sentence punctuation
            for punct in [". ", "! ", "? ", "; "]:
                p = clean_text.rfind(punct, start, end)
                if p > split_pos:
                    split_pos = p + len(punct)
        if split_pos == -1 or split_pos <= start + 50:
            # Fallback to word boundary
            split_pos = clean_text.rfind(" ", start, end)
        if split_pos == -1 or split_pos <= start:
            split_pos = end

        chunk = clean_text[start:split_pos].strip()
        if chunk:
            chunks.append(chunk)

        start = max(split_pos - chunk_overlap, start + 1)

    return chunks

def parse_markdown_document(path: Path,
                            chunk_size: int = 500,
                            chunk_overlap: int = 80) -> List[DocumentChunk]:
    """
    Parses Markdown files, extracting sections by markdown headings.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    last_modified = get_file_last_modified_iso(path)
    filename = path.name

    # Split document by markdown headings (#, ##, ###)
    heading_pattern = re.compile(r"^(#{1,4}\s+.+)$", re.MULTILINE)
    parts = heading_pattern.split(content)

    sections = []
    current_title = "Document Overview"

    if parts:
        # First block before any heading
        if parts[0].strip():
            sections.append((current_title, parts[0].strip()))

        # Iterate heading + content pairs
        for i in range(1, len(parts), 2):
            heading = parts[i].strip("# ").strip()
            body = parts[i+1].strip() if i+1 < len(parts) else ""
            if body:
                sections.append((heading, body))

    if not sections:
        sections = [("General", content.strip())]

    chunks = []
    chunk_index = 0

    for section_title, section_body in sections:
        split_pieces = split_text_into_chunks(section_body, chunk_size, chunk_overlap)
        for piece in split_pieces:
            chunk_id = f"{filename}:sec_{chunk_index:03d}"
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                text=piece,
                source_file=filename,
                doc_type="markdown",
                section_title=section_title,
                page_number=1,
                last_modified=last_modified,
                char_count=len(piece)
            ))
            chunk_index += 1

    return chunks

def parse_plain_text_document(path: Path,
                              chunk_size: int = 500,
                              chunk_overlap: int = 80) -> List[DocumentChunk]:
    """
    Parses plain text files, preserving paragraph groupings and merging small headings.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    last_modified = get_file_last_modified_iso(path)
    filename = path.name
    raw_paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    # Group very short leading paragraphs (like titles) with subsequent body text
    grouped_paragraphs = []
    current_para = ""
    for p in raw_paragraphs:
        if current_para and (len(current_para) + len(p) + 2 <= chunk_size):
            current_para += "\n\n" + p
        else:
            if current_para:
                grouped_paragraphs.append(current_para)
            current_para = p
    if current_para:
        grouped_paragraphs.append(current_para)

    chunks = []
    chunk_index = 0

    for p_idx, para in enumerate(grouped_paragraphs):
        split_pieces = split_text_into_chunks(para, chunk_size, chunk_overlap)
        for piece in split_pieces:
            chunk_id = f"{filename}:p_{chunk_index:03d}"
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                text=piece,
                source_file=filename,
                doc_type="text",
                section_title=f"Paragraph {p_idx+1}",
                page_number=1,
                last_modified=last_modified,
                char_count=len(piece)
            ))
            chunk_index += 1

    return chunks

def parse_pdf_document(path: Path,
                       chunk_size: int = 500,
                       chunk_overlap: int = 80) -> List[DocumentChunk]:
    """
    Parses PDF documents page by page, preserving page attribution.
    """
    if not HAS_PYPDF:
        raise RuntimeError("pypdf is not installed. PDF ingestion unavailable.")

    last_modified = get_file_last_modified_iso(path)
    filename = path.name
    chunks = []
    chunk_index = 0

    reader = pypdf.PdfReader(str(path))
    num_pages = len(reader.pages)

    for page_num in range(1, num_pages + 1):
        page = reader.pages[page_num - 1]
        page_text = page.extract_text() or ""
        page_text = page_text.strip()
        if not page_text:
            continue

        split_pieces = split_text_into_chunks(page_text, chunk_size, chunk_overlap)
        for piece in split_pieces:
            chunk_id = f"{filename}:pg_{page_num}_{chunk_index:03d}"
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                text=piece,
                source_file=filename,
                doc_type="pdf",
                section_title=f"Page {page_num}",
                page_number=page_num,
                last_modified=last_modified,
                char_count=len(piece)
            ))
            chunk_index += 1

    return chunks

def ingest_document(path: Path,
                    chunk_size: int = 500,
                    chunk_overlap: int = 80) -> List[DocumentChunk]:
    """
    Dispatches file parsing according to file extension.
    """
    suffix = path.suffix.lower()
    if suffix in [".md", ".markdown"]:
        return parse_markdown_document(path, chunk_size, chunk_overlap)
    elif suffix in [".txt", ".text"]:
        return parse_plain_text_document(path, chunk_size, chunk_overlap)
    elif suffix == ".pdf":
        return parse_pdf_document(path, chunk_size, chunk_overlap)
    else:
        # Unsupported or ignored file
        return []
