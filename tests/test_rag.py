"""
tests/test_rag.py - Comprehensive Test Suite for Phase 9 College RAG System

Tests:
1. Markdown document parsing, metadata preservation, and section-aware chunking.
2. Plain text document parsing and paragraph boundary handling.
3. PDF document parsing and page-number preservation.
4. Query intent classification (college institutional vs general conversation).
5. Deterministic local retrieval and relevance ranking.
6. Source attribution (source filename, section title/page, last modified).
7. Missing evidence protocol (refusal to hallucinate when facts are absent).
8. Conflicting documents detection (identifying contradictory records).
9. Dynamic re-indexing without application code changes.
10. Full RAG API endpoints (/api/v1/rag/query, /api/v1/rag/reindex, /api/v1/rag/status).
"""

import os
os.environ.setdefault("DORURU_DEVICE_TOKEN", "test_mock_device_token_12345")

import unittest
import shutil
import tempfile
import json
from pathlib import Path

from backend.app.rag.ingestion import (
    parse_markdown_document,
    parse_plain_text_document,
    parse_pdf_document,
    ingest_document,
    split_text_into_chunks
)
from backend.app.rag.retriever import LocalTFIDFRetriever
from backend.app.rag.classifier import classify_query
from backend.app.rag.prompt_builder import (
    build_grounded_rag_prompt,
    detect_evidence_conflict,
    MISSING_EVIDENCE_RESPONSE
)
from backend.app.rag.service import CollegeRAGService
from backend.app.main import app
import pypdf

class TestCollegeRAG(unittest.TestCase):
    def setUp(self):
        # Create isolated temporary directory for test knowledge base
        self.temp_dir = tempfile.mkdtemp(prefix="doruru_rag_test_")
        self.docs_dir = Path(self.temp_dir) / "documents"
        self.index_dir = Path(self.temp_dir) / "index"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Setup sample test documents
        self.create_sample_documents()

        # Initialize test retriever
        self.retriever = LocalTFIDFRetriever(docs_dir=self.docs_dir, index_dir=self.index_dir)
        self.retriever.build_index()

        # Initialize test service
        self.service = CollegeRAGService(retriever=self.retriever)

        # Flask test client
        self.client = app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_sample_documents(self):
        # 1. Academic Calendar (.md)
        cal_path = self.docs_dir / "academic_calendar.md"
        with open(cal_path, "w", encoding="utf-8") as f:
            f.write("""# Academic Calendar 2026-2027

## Semester 1 Schedule
The commencement of classes begins on August 1, 2026.
Mid-term evaluation will take place from October 12-16, 2026.
Final semester examinations will be conducted from December 1-15, 2026.

## Library Working Hours
The central library is open Monday through Saturday from 08:00 AM to 08:00 PM.
Students must present a valid physical ID card at the circulation desk to borrow books.
""")

        # 2. Computer Science Department (.md)
        cs_path = self.docs_dir / "computer_science_dept.md"
        with open(cs_path, "w", encoding="utf-8") as f:
            f.write("""# Department of Computer Engineering

## Laboratory Facilities
The Robotics & IoT Lab is located in Room 304 of Academic Block B.
The Artificial Intelligence Lab is located in Room 308 of Academic Block B.
The Software Systems Lab is located in Room 202 of the Central Computing Facility.

## Contact Information
Department Office is in Room 301, Academic Block B.
Office hours for student queries are 10:00 AM to 01:00 PM and 02:00 PM to 04:30 PM.
""")

        # 3. Attendance Notice (.txt)
        att_path = self.docs_dir / "attendance_rules.txt"
        with open(att_path, "w", encoding="utf-8") as f:
            f.write("""Official Notice: Mandatory Attendance Requirement.

All undergraduate students must maintain a minimum of 75 percent attendance in theory lectures and 80 percent attendance in practical lab sessions to be eligible to appear for the end-semester examinations.

Students with less than 75 percent attendance will be detained from appearing in the Semester End Examinations unless condoned by the Dean of Academic Affairs for certified medical emergencies.
""")

    def test_markdown_ingestion_and_chunking(self):
        """Verifies section-aware extraction and metadata preservation for Markdown."""
        cal_path = self.docs_dir / "academic_calendar.md"
        chunks = parse_markdown_document(cal_path, chunk_size=500, chunk_overlap=80)
        self.assertGreaterEqual(len(chunks), 2)

        titles = [c.section_title for c in chunks]
        self.assertIn("Semester 1 Schedule", titles)
        self.assertIn("Library Working Hours", titles)

        for c in chunks:
            self.assertEqual(c.source_file, "academic_calendar.md")
            self.assertEqual(c.doc_type, "markdown")
            self.assertEqual(c.page_number, 1)
            self.assertTrue(len(c.last_modified) > 0)
            self.assertGreater(c.char_count, 20)

    def test_plain_text_ingestion(self):
        """Verifies paragraph parsing and metadata preservation for plain text."""
        att_path = self.docs_dir / "attendance_rules.txt"
        chunks = parse_plain_text_document(att_path, chunk_size=500, chunk_overlap=80)
        self.assertGreaterEqual(len(chunks), 1)

        text_content = " ".join(c.text for c in chunks)
        self.assertIn("75 percent attendance", text_content)
        self.assertEqual(chunks[0].doc_type, "text")
        self.assertEqual(chunks[0].source_file, "attendance_rules.txt")

    def test_pdf_ingestion_with_page_attribution(self):
        """Creates a sample multi-page PDF with text and exercises parse_pdf_document with page attribution."""
        pdf_path = self.docs_dir / "sample_circular.pdf"

        # Generate a valid 2-page PDF using pypdf.PdfWriter with accurate content stream lengths
        writer = pypdf.PdfWriter()
        font_dict = pypdf.generic.DictionaryObject({
            pypdf.generic.NameObject("/Type"): pypdf.generic.NameObject("/Font"),
            pypdf.generic.NameObject("/Subtype"): pypdf.generic.NameObject("/Type1"),
            pypdf.generic.NameObject("/BaseFont"): pypdf.generic.NameObject("/Helvetica"),
        })
        font_ref = writer._add_object(font_dict)
        resources = pypdf.generic.DictionaryObject({
            pypdf.generic.NameObject("/Font"): pypdf.generic.DictionaryObject({
                pypdf.generic.NameObject("/F1"): font_ref
            })
        })

        p1 = writer.add_blank_page(width=612, height=792)
        s1 = pypdf.generic.DecodedStreamObject()
        s1.set_data(b"BT /F1 12 Tf 100 700 Td (Official Campus Circular Page 1 Content) Tj ET")
        p1[pypdf.generic.NameObject("/Contents")] = writer._add_object(s1)
        p1[pypdf.generic.NameObject("/Resources")] = resources

        p2 = writer.add_blank_page(width=612, height=792)
        s2 = pypdf.generic.DecodedStreamObject()
        s2.set_data(b"BT /F1 12 Tf 100 700 Td (Scholarship Guidelines Page 2 Content) Tj ET")
        p2[pypdf.generic.NameObject("/Contents")] = writer._add_object(s2)
        p2[pypdf.generic.NameObject("/Resources")] = resources

        with open(pdf_path, "wb") as f:
            writer.write(f)

        # Directly exercise parse_pdf_document with non-empty pages
        chunks = parse_pdf_document(pdf_path, chunk_size=500, chunk_overlap=80)
        self.assertEqual(len(chunks), 2)

        # Assert page 1 attribution
        self.assertEqual(chunks[0].page_number, 1)
        self.assertEqual(chunks[0].doc_type, "pdf")
        self.assertEqual(chunks[0].section_title, "Page 1")
        self.assertEqual(chunks[0].source_file, "sample_circular.pdf")
        self.assertIn("Official Campus Circular Page 1 Content", chunks[0].text)

        # Assert page 2 attribution
        self.assertEqual(chunks[1].page_number, 2)
        self.assertEqual(chunks[1].doc_type, "pdf")
        self.assertEqual(chunks[1].section_title, "Page 2")
        self.assertEqual(chunks[1].source_file, "sample_circular.pdf")
        self.assertIn("Scholarship Guidelines Page 2 Content", chunks[1].text)


    def test_query_classification(self):
        """Verifies distinction between college questions and general queries."""
        # College questions
        college_queries = [
            "When do final semester exams start?",
            "What is the library timing?",
            "Where is the Robotics lab located?",
            "What is the minimum attendance required for exams?",
            "What are the office hours for the department office?",
            "Show me the academic calendar dates"
        ]
        for q in college_queries:
            cls = classify_query(q)
            self.assertTrue(cls.is_college_specific, f"Expected '{q}' to be classified as college query")
            self.assertGreaterEqual(cls.confidence, 0.70)

        # General questions
        general_queries = [
            "What is the capital of Japan?",
            "Tell me a joke about robots",
            "How does an H-bridge motor driver work?",
            "Who was Leonardo da Vinci?",
            "Can you write a poem about the sunrise?"
        ]
        for q in general_queries:
            cls = classify_query(q)
            self.assertFalse(cls.is_college_specific, f"Expected '{q}' to be classified as general query")

    def test_relevant_retrieval(self):
        """Verifies accurate chunk retrieval for college queries."""
        # Query 1: Library hours
        lib_results = self.retriever.retrieve("What are the library working hours?", top_k=2)
        self.assertGreater(len(lib_results), 0)
        self.assertEqual(lib_results[0].chunk.source_file, "academic_calendar.md")
        self.assertEqual(lib_results[0].chunk.section_title, "Library Working Hours")
        self.assertIn("08:00 AM to 08:00 PM", lib_results[0].chunk.text)

        # Query 2: Robotics lab
        lab_results = self.retriever.retrieve("Where is the Robotics and IoT lab located?", top_k=2)
        self.assertGreater(len(lab_results), 0)
        self.assertEqual(lab_results[0].chunk.source_file, "computer_science_dept.md")
        self.assertIn("Room 304", lab_results[0].chunk.text)

        # Query 3: Attendance percentage
        att_results = self.retriever.retrieve("What is the mandatory attendance percentage?", top_k=2)
        self.assertGreater(len(att_results), 0)
        self.assertEqual(att_results[0].chunk.source_file, "attendance_rules.txt")
        self.assertIn("75 percent", att_results[0].chunk.text)

    def test_source_attribution_metadata(self):
        """Verifies that all retrieved results carry complete source attribution."""
        results = self.retriever.retrieve("final semester examinations date", top_k=2)
        self.assertGreater(len(results), 0)

        top_chunk = results[0].chunk
        self.assertEqual(top_chunk.source_file, "academic_calendar.md")
        self.assertEqual(top_chunk.section_title, "Semester 1 Schedule")
        self.assertIsNotNone(top_chunk.last_modified)
        self.assertGreater(top_chunk.char_count, 0)

        # Check prompt builder formatting
        prompt_data = build_grounded_rag_prompt("When are exams?", results)
        self.assertTrue("academic_calendar.md" in prompt_data["context_str"])
        self.assertTrue("Semester 1 Schedule" in prompt_data["context_str"])

    def test_missing_evidence_protocol(self):
        """
        Verifies that questions with no evidence in the knowledge base produce
        the mandatory unverified response rather than hallucinating facts.
        """
        # Question on an unrecorded topic
        query = "Who is the head coach of the college swimming team?"
        response = self.service.answer_query(query)

        self.assertTrue(response["is_college_query"])
        # Should return missing evidence response
        self.assertEqual(response["answer"], MISSING_EVIDENCE_RESPONSE)
        self.assertEqual(len(response["sources"]), 0)

        # Another unrecorded topic
        query2 = "What was the college electricity bill in 1995?"
        response2 = self.service.answer_query(query2)
        self.assertEqual(response2["answer"], MISSING_EVIDENCE_RESPONSE)

    def test_conflicting_documents_handling(self):
        """
        Verifies that conflicting documents (e.g. contradictory exam dates)
        are explicitly flagged.
        """
        # Create a second conflicting calendar document
        conflict_path = self.docs_dir / "revised_conflicting_calendar.md"
        with open(conflict_path, "w", encoding="utf-8") as f:
            f.write("""# Revised Academic Calendar 2026-2027

## Semester 1 Schedule
Final semester examinations will be conducted from January 10-25, 2027.
Commencement of classes begins on September 15, 2026.
""")

        # Re-index to include conflicting document
        self.retriever.build_index()

        results = self.retriever.retrieve("When are the final semester examinations?", top_k=3)
        self.assertGreaterEqual(len(results), 2)

        has_conflict, details = detect_evidence_conflict(results)
        self.assertTrue(has_conflict)
        self.assertIn("Discrepancy detected", details)

    def test_dynamic_reindexing_without_code_changes(self):
        """
        Verifies that adding a new document dynamically updates search results
        after calling reindex(), without restarting or changing code.
        """
        # Query before adding file
        initial_results = self.retriever.retrieve("canteen timings and lunch menu", top_k=2)
        self.assertEqual(len(initial_results), 0)

        # Add new document
        canteen_path = self.docs_dir / "canteen_services.md"
        with open(canteen_path, "w", encoding="utf-8") as f:
            f.write("""# Campus Canteen Services

## Canteen Timings
The central canteen operates from 07:30 AM to 07:00 PM.
Lunch is served from 12:00 PM to 02:30 PM with vegetarian and vegan meal options.
""")

        # Re-index
        total_chunks = self.service.reindex(force=True)
        self.assertGreater(total_chunks, 0)

        # Query after adding file
        new_results = self.retriever.retrieve("What are the canteen lunch timings?", top_k=2)
        self.assertGreater(len(new_results), 0)
        self.assertEqual(new_results[0].chunk.source_file, "canteen_services.md")
        self.assertIn("12:00 PM to 02:30 PM", new_results[0].chunk.text)

    def test_rag_api_endpoints(self):
        """Verifies the Flask RAG API query and status endpoints."""
        # 1. Status endpoint
        resp = self.client.get("/api/v1/rag/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "online")
        self.assertIn("total_chunks", data)

        # 2. Query endpoint - college question
        query_payload = {"query": "What are the library hours?", "top_k": 2}
        resp = self.client.post("/api/v1/rag/query",
                                data=json.dumps(query_payload),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["is_college_query"])

        # 3. Query endpoint - general question
        gen_payload = {"query": "What is the boiling point of water?"}
        resp = self.client.post("/api/v1/rag/query",
                                data=json.dumps(gen_payload),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertFalse(data["is_college_query"])

    def test_empty_index_loading_resets_state(self):
        """Verifies that loading an empty chunk index resets idf, inverted_index, and norms consistently."""
        empty_index_dir = Path(self.temp_dir) / "empty_index"
        empty_index_dir.mkdir()
        with open(empty_index_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump([], f)
        with open(empty_index_dir / "index_manifest.json", "w", encoding="utf-8") as f:
            json.dump({"total_chunks": 0, "indexed_files": {}, "vocabulary_size": 0}, f)

        empty_retriever = LocalTFIDFRetriever(docs_dir=self.docs_dir, index_dir=empty_index_dir)
        # Prepopulate with dummy state to verify reset
        empty_retriever.idf = {"stale_term": 1.0}
        empty_retriever.inverted_index = {"stale_term": [(0, 1.0)]}
        empty_retriever.chunk_norms = [1.0]

        loaded = empty_retriever.load_index()
        self.assertTrue(loaded)
        self.assertEqual(empty_retriever.idf, {})
        self.assertEqual(empty_retriever.inverted_index, {})
        self.assertEqual(empty_retriever.chunk_norms, [])


if __name__ == "__main__":
    unittest.main()

