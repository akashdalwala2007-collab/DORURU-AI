"""
backend/app/rag/classifier.py - Query Intent Classifier

Distinguishes college-specific institutional questions from general conversation.
"""

import re
from typing import Tuple

COLLEGE_KEYWORDS = [
    # Academic & Institutional
    "college", "campus", "university", "institute", "institution", "department",
    "admissions", "admission", "fees", "fee", "tuition", "syllabus", "curriculum",
    "exam", "exams", "examination", "examinations", "midterm", "mid-term", "semester",
    "attendance", "library", "circulation", "books", "hod", "head of department",
    "dean", "principal", "director", "faculty", "professor", "lecturer", "teacher",
    "hostel", "dorm", "canteen", "cafeteria", "placement", "placements", "recruiters",
    "scholarship", "scholarships", "grade", "grades", "gpa", "cgpa", "classroom",
    "laboratory", "laboratories", "lab", "labs", "academic calendar", "academic block",
    "credits", "credit", "lecture", "lectures", "practicals", "hall ticket",
    "re-evaluation", "cie", "see", "pass mark", "passing criteria", "curfew", "rules"
]

COLLEGE_REGEX_PATTERNS = [
    r"\b(where\s+is|location\s+of)\s+the\s+.*(lab|block|office|library|canteen|room)\b",
    r"\b(when\s+do|when\s+does|date\s+of)\s+.*(class|classes|exam|exams|semester|vacation)\b",
    r"\b(how\s+much|what\s+is)\s+the\s+.*(fee|fees|attendance|passing\s+mark)\b",
    r"\b(contact|email|phone)\s+.*(department|office|hod|dean|principal)\b",
    r"\b(minimum|required)\s+attendance\b",
    r"\bacademic\s+calendar\b"
]

class QueryClassification:
    def __init__(self, is_college_specific: bool, reason: str, confidence: float):
        self.is_college_specific = is_college_specific
        self.reason = reason
        self.confidence = confidence

    def to_dict(self):
        return {
            "is_college_specific": self.is_college_specific,
            "reason": self.reason,
            "confidence": round(self.confidence, 2)
        }

def classify_query(query: str) -> QueryClassification:
    """
    Classifies a user question as either college-specific or general knowledge.
    """
    clean_q = query.strip().lower()
    if not clean_q:
        return QueryClassification(False, "Empty query", 1.0)

    # 1. Regex Pattern Matches
    for pattern in COLLEGE_REGEX_PATTERNS:
        if re.search(pattern, clean_q):
            return QueryClassification(
                is_college_specific=True,
                reason=f"Matched institutional inquiry pattern: '{pattern}'",
                confidence=0.95
            )

    # 2. Token Matching against Institutional Keywords
    words = set(re.findall(r"\b[a-z]{3,}\b", clean_q))
    matched_keywords = [kw for kw in COLLEGE_KEYWORDS if kw in clean_q or kw in words]

    if matched_keywords:
        confidence = min(0.6 + (0.15 * len(matched_keywords)), 0.95)
        return QueryClassification(
            is_college_specific=True,
            reason=f"Matched college keyword(s): {', '.join(matched_keywords)}",
            confidence=confidence
        )

    # 3. Default to General Conversation
    return QueryClassification(
        is_college_specific=False,
        reason="No college or campus-specific institutional keywords identified",
        confidence=0.90
    )

