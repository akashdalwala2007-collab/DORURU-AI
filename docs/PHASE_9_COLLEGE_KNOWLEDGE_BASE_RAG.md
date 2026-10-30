# DORURU — Phase 9: College Knowledge Base & RAG Documentation

## 1. System Overview
Phase 9 delivers DORURU's college-specific knowledge system using **Retrieval-Augmented Generation (RAG)**.

### Core Architecture Principles
1. **Strict Zero-Hallucination Policy**: The knowledge base contains only documents explicitly supplied or approved by the user. DORURU never fabricates or extrapolates college history, faculty names, dates, departments, achievements, events, fees, or statistics.
2. **Missing Evidence Protocol**: If an institutional fact is not verified in the indexed knowledge base, the system explicitly reports that the information is unverified and directs the user to an authoritative official source.
3. **Source Attribution**: Every institutional answer cites the exact source document and section or page (e.g., `[academic_calendar.md, Sec: Semester 1 Schedule]`).
4. **Discrepancy Flagging**: If multiple documents provide conflicting information (e.g. contradictory examination dates or fees), the system flags the contradiction rather than arbitrarily picking one.
5. **Separation of Concerns**: General questions (e.g. general knowledge, math, science, casual chat) bypass institutional grounding constraints, while college questions enforce strict grounding.
6. **Code-Free Document Updates**: Documents can be added, updated, or removed in `knowledge_base/documents/` and re-indexed at any time via a standalone CLI tool or HTTP endpoint without changing application code.

---

## 2. Document Ingestion & Chunking Pipeline

### Supported Document Formats
- **Markdown (`.md`)**: Extracts sections by heading hierarchy (`#`, `##`, `###`). Section titles are preserved and receive a 1.5x relevance boost during search.
- **Plain Text (`.txt`)**: Grouped paragraph extraction with paragraph number attribution.
- **PDF Documents (`.pdf`)**: Page-by-page text extraction using `pypdf`, preserving exact page number attribution (`Page 1`, `Page 2`, etc.).

### Metadata Preserved on Every Chunk
Every indexed chunk carries:
- `chunk_id`: Unique identifier (e.g., `academic_calendar.md:sec_001`)
- `source_file`: Relative filename of the document
- `doc_type`: Document type (`markdown`, `text`, `pdf`)
- `section_title`: Section heading name or paragraph identifier
- `page_number`: Page number (for PDFs) or 1 (for single-page formats)
- `last_modified`: ISO 8601 modification timestamp
- `char_count`: Character length of chunk
- `text`: Chunk content

### Boundary-Aware Chunking
Text is split into chunks of approximately 500 characters with 80 characters of overlap. Splits occur exclusively on natural boundaries (paragraph breaks `\n\n`, newlines `\n`, or sentence punctuation `. `, `! `, `? `) to prevent cutting words or sentences in half.

---

## 3. Local Retrieval Engine

In accordance with Phase 9 requirements, the retrieval engine begins with a maintainable, high-performance local implementation without requiring an external vector database:
- **TF-IDF & BM25 Scoring**: Smoothed Inverse Document Frequency with length normalization.
- **Section Title Boosting**: Terms appearing in section headings receive a 1.5x weight multiplier.
- **Inverted Index**: Memory-efficient term-to-chunk index mapping for fast lookups.
- **Persistence**: Chunks and index manifests are persisted to `knowledge_base/index/chunks.json` and `index_manifest.json` for fast boot loading.

---

## 4. Query Intent Classification

User queries are evaluated by [`backend/app/rag/classifier.py`](file:///c:/Users/padgi/OneDrive/Desktop/Doruru%20(1)/DORURU-AI/backend/app/rag/classifier.py):
- **College Inquiries**: Matched against institutional regex patterns and domain keywords (e.g., exams, library, attendance, fees, labs, departments, professors, calendar). These trigger full RAG retrieval and strict grounding.
- **General Inquiries**: Non-institutional queries (e.g. general knowledge, chit-chat, programming questions) bypass RAG grounding constraints so conversational capabilities are preserved.

---

## 5. Grounding & Safety Instructions for Gemini

When a college inquiry is detected, the prompt builder constructs a structured prompt payload with the following system instructions:

```markdown
MANDATORY RULES FOR INSTITUTIONAL & COLLEGE INQUIRIES:
1. STRICT GROUNDING: Answer institutional facts ONLY from the verified evidence provided in the CONTEXT below.
2. ZERO HALLUCINATION: Never fabricate, guess, or assume dates, faculty names, room numbers, fees, policies, or statistics.
3. SOURCE ATTRIBUTION: Cite the source document name and section/page for every factual claim you make (e.g., "[academic_calendar.md, Sec: Semester 1 Schedule]").
4. MISSING EVIDENCE: If the question asks for college information that is absent from the provided context, state explicitly:
   "This information is not verified in the official records. Please consult the college administration or an authoritative source."
5. CONFLICTING EVIDENCE: If retrieved documents present conflicting information, explicitly point out the discrepancy rather than choosing an unverified answer.
6. CONCISE VOICE-FIRST STYLE: Keep responses clear, concise, and suitable for spoken output on the robot.
```

---

## 6. How to Update & Re-Index Documents

### Directory Layout
```
knowledge_base/
├── README.md               # User guide and rules
├── documents/              # Put your approved college documents here
│   └── README.md
├── index/                  # Automatically generated chunk cache and manifest
│   ├── chunks.json
│   └── index_manifest.json
└── templates/              # Sample placeholders (clearly marked as non-factual)
    ├── SAMPLE_TEMPLATE_academic_calendar.md
    ├── SAMPLE_TEMPLATE_computer_science_dept.md
    └── SAMPLE_TEMPLATE_examination_policy.md
```

### CLI Re-Indexing
Whenever documents are added or updated in `knowledge_base/documents/`, run:
```powershell
python scripts/reindex_knowledge_base.py --force
```

### API Re-Indexing
Alternatively, trigger re-indexing via HTTP POST:
```bash
curl -X POST http://localhost:8000/api/v1/rag/reindex
```

---

## 7. API Endpoints

### 1. `POST /api/v1/rag/query`
- **Request**:
  ```json
  {
    "query": "What are the central library working hours?",
    "top_k": 3
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "query": "What are the central library working hours?",
    "is_college_query": true,
    "classification_reason": "Matched college keyword(s): library",
    "answer": "Based on official college records: The central library is open Monday through Saturday from 08:00 AM to 08:00 PM. [academic_calendar.md, Sec: Library Working Hours]",
    "sources": [
      {
        "source_file": "academic_calendar.md",
        "section_title": "Library Working Hours",
        "page_number": 1,
        "last_modified": "2026-10-30T10:57:26Z",
        "relevance_score": 0.85
      }
    ],
    "evidence_count": 1,
    "conflict_detected": false
  }
  ```

### 2. `POST /api/v1/rag/reindex`
- Triggers on-the-fly index rebuild and returns indexed files list and chunk counts.

### 3. `GET /api/v1/rag/status`
- Returns index health, total chunks, vocabulary size, and manifest details.

---

## 8. Test Evidence

Executed test suite:
```powershell
python -m unittest tests/test_rag.py -v
```

**Results:**
```
test_conflicting_documents_handling ... ok
test_dynamic_reindexing_without_code_changes ... ok
test_markdown_ingestion_and_chunking ... ok
test_missing_evidence_protocol ... ok
test_pdf_ingestion_with_page_attribution ... ok
test_plain_text_ingestion ... ok
test_query_classification ... ok
test_rag_api_endpoints ... ok
test_relevant_retrieval ... ok
test_source_attribution_metadata ... ok

Ran 10 tests in 0.113s - OK
Total Project Tests: 22 tests in 0.648s - OK (100% Pass)
```

