"""
backend/app/rag/prompt_builder.py - Grounded Prompt Construction for Gemini

Enforces:
- Strict evidence-only grounding for institutional college facts.
- No invention or extrapolation of dates, faculty names, departments, or statistics.
- Mandatory source citations (filename, section/page, last modified).
- Missing evidence fallback ("This information is not verified in the official records...").
- Discrepancy flagging for conflicting documents.
"""

from typing import List, Dict, Any, Tuple
from .retriever import RetrievalResult

SYSTEM_GROUNDING_INSTRUCTION = """You are DORURU, a friendly, helpful, and highly accurate college assistant robot.

MANDATORY RULES FOR INSTITUTIONAL & COLLEGE INQUIRIES:
1. STRICT GROUNDING: Answer institutional facts ONLY from the verified evidence provided in the CONTEXT below.
2. ZERO HALLUCINATION: Never fabricate, guess, or assume dates, faculty names, room numbers, fees, policies, or statistics.
3. SOURCE ATTRIBUTION: Cite the source document name and section/page for every factual claim you make (e.g., "[academic_calendar.md, Sec: Semester 1 Schedule]").
4. MISSING EVIDENCE: If the question asks for college information that is absent from the provided context, state explicitly:
   "This information is not verified in the official records. Please consult the college administration or an authoritative source."
5. CONFLICTING EVIDENCE: If retrieved documents present conflicting information, explicitly point out the discrepancy rather than choosing an unverified answer.
6. CONCISE VOICE-FIRST STYLE: Keep responses clear, concise, and suitable for spoken output on the robot.
"""

MISSING_EVIDENCE_RESPONSE = (
    "This information is not verified in the official records. "
    "Please consult the college administration or an authoritative source."
)

def format_context_chunks(results: List[RetrievalResult]) -> str:
    """Formats retrieved chunks with complete source metadata."""
    if not results:
        return "[NO RETRIEVED EVIDENCE AVAILABLE]"

    blocks = []
    for idx, r in enumerate(results, 1):
        c = r.chunk
        page_info = f"Page {c.page_number}" if c.doc_type == "pdf" else f"Sec: {c.section_title}"
        header = f"[SOURCE {idx}: {c.source_file} | {page_info} | Updated: {c.last_modified} | Relevance: {r.score}]"
        blocks.append(f"{header}\n{c.text}")

    return "\n\n".join(blocks)

def build_grounded_rag_prompt(query: str, results: List[RetrievalResult]) -> Dict[str, Any]:
    """
    Builds the structured prompt payload for Gemini or the response generator.
    """
    context_str = format_context_chunks(results)

    sources_metadata = []
    for r in results:
        c = r.chunk
        sources_metadata.append({
            "source_file": c.source_file,
            "section_title": c.section_title,
            "page_number": c.page_number,
            "last_modified": c.last_modified,
            "relevance_score": r.score
        })

    user_prompt = f"""USER QUESTION:
{query}

VERIFIED INSTITUTIONAL CONTEXT:
{context_str}

Please answer the question according to the strict grounding instructions.
Cite sources for every institutional fact. If evidence is missing, use the missing evidence protocol."""

    return {
        "system_instruction": SYSTEM_GROUNDING_INSTRUCTION,
        "user_prompt": user_prompt,
        "sources": sources_metadata,
        "context_str": context_str,
        "evidence_count": len(results)
    }

def detect_evidence_conflict(results: List[RetrievalResult]) -> Tuple[bool, str]:
    """
    Checks if multiple retrieved sources contain contradictory statements on common keys.
    """
    if len(results) < 2:
        return False, ""

    # Look for conflicting date or fee patterns across distinct files
    sources_by_file: Dict[str, List[str]] = {}
    for r in results:
        sources_by_file.setdefault(r.chunk.source_file, []).append(r.chunk.text.lower())

    if len(sources_by_file) >= 2:
        files = list(sources_by_file.keys())
        text_a = " ".join(sources_by_file[files[0]])
        text_b = " ".join(sources_by_file[files[1]])

        # Example check: conflicting fee amounts or schedule dates
        import re
        dates_a = set(re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\b", text_a))
        dates_b = set(re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\b", text_b))

        # Check for overlapping subject with different dates
        if dates_a and dates_b and dates_a != dates_b:
            conflict_msg = f"Discrepancy detected between '{files[0]}' and '{files[1]}' regarding dates ({', '.join(dates_a)} vs {', '.join(dates_b)})."
            return True, conflict_msg

    return False, ""

