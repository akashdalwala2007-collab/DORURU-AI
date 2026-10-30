"""
backend/app/rag/service.py - College Knowledge Base & RAG Orchestration Service

Orchestrates:
1. Query classification (college-specific vs general conversation).
2. Local retrieval from indexed documents with metadata preservation.
3. Conflict detection and missing evidence handling.
4. Grounded answer generation adhering strictly to verified institutional context.
"""

from typing import Dict, Any, Optional
from .classifier import classify_query
from .retriever import LocalTFIDFRetriever
from .prompt_builder import (
    build_grounded_rag_prompt,
    detect_evidence_conflict,
    MISSING_EVIDENCE_RESPONSE
)
from .. import config

class CollegeRAGService:
    def __init__(self, retriever: Optional[LocalTFIDFRetriever] = None):
        self.retriever = retriever or LocalTFIDFRetriever()
        # Initialize or load index on service startup
        if not self.retriever.load_index():
            self.retriever.build_index()

    def reindex(self, force: bool = True) -> int:
        """Triggers document re-indexing and returns total chunk count."""
        return self.retriever.build_index(force=force)

    def answer_query(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """
        Processes user query through RAG pipeline.
        """
        classification = classify_query(query)

        # 1. Non-College General Questions
        if not classification.is_college_specific:
            return {
                "is_college_query": False,
                "classification_reason": classification.reason,
                "answer": (
                    f"This appears to be a general inquiry rather than a college-specific question. "
                    f"General response for: '{query}'"
                ),
                "sources": [],
                "evidence_count": 0,
                "conflict_detected": False
            }

        # 2. College Institutional Questions
        results = self.retriever.retrieve(query, top_k=top_k)

        # 3. Handle Missing Evidence
        if not results:
            return {
                "is_college_query": True,
                "classification_reason": classification.reason,
                "answer": MISSING_EVIDENCE_RESPONSE,
                "sources": [],
                "evidence_count": 0,
                "conflict_detected": False
            }

        # 4. Check for Conflicting Documents
        has_conflict, conflict_msg = detect_evidence_conflict(results)

        # 5. Build Grounded Prompt
        prompt_payload = build_grounded_rag_prompt(query, results)

        # 6. Generate Grounded Answer (Extracts from top source with citation)
        top_result = results[0]
        c = top_result.chunk
        page_info = f"Page {c.page_number}" if c.doc_type == "pdf" else f"Sec: {c.section_title}"
        citation = f"[{c.source_file}, {page_info}]"

        # Direct, grounded synthesis
        synthesis = f"Based on official college records: {c.text} {citation}"
        if has_conflict:
            synthesis = f"WARNING: {conflict_msg}\n{synthesis}"

        return {
            "is_college_query": True,
            "classification_reason": classification.reason,
            "answer": synthesis,
            "sources": prompt_payload["sources"],
            "evidence_count": len(results),
            "conflict_detected": has_conflict,
            "conflict_details": conflict_msg if has_conflict else None,
            "prompt_payload": prompt_payload
        }

