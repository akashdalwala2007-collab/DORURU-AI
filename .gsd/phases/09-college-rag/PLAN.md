---
phase: 9
plan: 1
wave: 1
gap_closure: false
---

# Plan 9.1: College Knowledge Base and RAG System

## Objective
Implement DORURU's college-specific knowledge system using Retrieval-Augmented Generation (RAG). The knowledge base must contain only documents explicitly supplied or approved by the user, strictly forbidding the fabrication of college history, faculty names, dates, departments, achievements, events, or statistics.

## Context
- `doruru_phase.txt` (Phase 9 Master Prompt)
- `backend/app/config.py` (RAG settings and directory paths)
- `knowledge_base/` (Document ingestion structure)

## Tasks

<task type="auto" effort="high">
  <name>Build Document Ingestion and Chunking Engine</name>
  <files>backend/app/rag/ingestion.py</files>
  <action>
    Implement multi-format parsing for Markdown (.md), Plain Text (.txt), and PDF (.pdf via pypdf).
    Preserve source metadata on all chunks: source_file, doc_type, section_title, page_number, last_modified.
    Implement boundary-aware chunking respecting sentence and paragraph boundaries with configurable chunk size and overlap.
  </action>
  <verify>python -m unittest tests/test_rag.py -k ingestion</verify>
  <done>All document types ingested with preserved section and page metadata</done>
</task>

<task type="auto" effort="high">
  <name>Build Local Retrieval Engine with Persistence</name>
  <files>backend/app/rag/retriever.py</files>
  <action>
    Implement deterministic local TF-IDF / BM25 retriever with inverted index.
    Incorporate section title relevance boosting (1.5x weight).
    Persist chunks and manifest to JSON cache for fast loading.
    Support dynamic re-indexing.
  </action>
  <verify>python -m unittest tests/test_rag.py -k retrieval</verify>
  <done>Fast, deterministic top-k retrieval with relevance ranking</done>
</task>

<task type="auto" effort="medium">
  <name>Implement Query Intent Classifier</name>
  <files>backend/app/rag/classifier.py</files>
  <action>
    Detect institutional college inquiries vs general conversational questions using regex patterns and domain keywords.
    Return classification object with boolean flag, reason string, and confidence score.
  </action>
  <verify>python -m unittest tests/test_rag.py -k classification</verify>
  <done>Accurately separates college questions from general conversational prompts</done>
</task>

<task type="auto" effort="medium">
  <name>Implement Grounding Prompt Builder and Missing Evidence Protocol</name>
  <files>backend/app/rag/prompt_builder.py, backend/app/rag/service.py</files>
  <action>
    Construct Gemini prompt with mandatory grounding instructions: answer strictly from context, cite sources, never extrapolate.
    Enforce missing evidence rule: explicitly state information is unverified if absent from context.
    Detect conflicting documents and flag discrepancies.
  </action>
  <verify>python -m unittest tests/test_rag.py -k missing_evidence</verify>
  <done>Zero hallucination enforced on absent facts and conflict detection active</done>
</task>

<task type="auto" effort="medium">
  <name>Create Re-Indexing CLI and Knowledge Base Templates</name>
  <files>scripts/reindex_knowledge_base.py, knowledge_base/README.md, knowledge_base/templates/*.md</files>
  <action>
    Create standalone script to re-index documents without changing code.
    Set up documented knowledge-base structure with sample templates clearly marked as placeholders.
  </action>
  <verify>python scripts/reindex_knowledge_base.py --force</verify>
  <done>CLI re-indexes cleanly and templates have explicit non-factual disclaimers</done>
</task>

