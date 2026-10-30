# DORURU College Knowledge Base

This directory contains the knowledge base files used by DORURU's Retrieval-Augmented Generation (RAG) system.

## Important Knowledge Base Principles
1. **Zero Hallucination of Facts**: The knowledge base must contain only documents explicitly provided or approved by the user. Do not fabricate college history, faculty names, dates, departments, achievements, events, fees, or statistics.
2. **Missing Evidence Protocol**: If an institutional fact is not documented in the indexed files, the system will explicitly report that the information is unverified and ask the user to consult the college administration or an authoritative official source.
3. **Conflict Resolution**: If two documents contain contradictory records (e.g., conflicting dates or rules), the system will flag the discrepancy rather than choosing an unverified answer.

## Directory Structure
- `documents/`: Place your approved college documents (`.md`, `.txt`, `.pdf`) here.
- `index/`: Generated chunk data and inverted index cache. Automatically rebuilt upon re-indexing.
- `templates/`: Sample document templates clearly marked as placeholders. **Not factual records.**

## Supported Document Formats
- **Markdown (`.md`)**: Recommended for structured policies, department details, and FAQs. Heading levels (`#`, `##`, `###`) are automatically preserved as section titles.
- **Plain Text (`.txt`)**: Suitable for unformatted text notices and announcements. Paragraph breaks are preserved.
- **PDF (`.pdf`)**: Official circulars and booklets. Page numbers and metadata are extracted page-by-page.

## How to Update / Re-Index Documents
Whenever you add, modify, or remove documents in `documents/`, re-index them without modifying any application code by running:

```powershell
python scripts/reindex_knowledge_base.py
```

Or trigger re-indexing via the backend API:
```bash
curl -X POST http://localhost:8000/api/v1/rag/reindex
```

