"""
backend/app/rag/retriever.py - Retrieval Engine for DORURU College Knowledge Base

Features:
- Deterministic, zero-dependency local TF-IDF & BM25 retrieval with section boosting.
- Pluggable BaseRetriever interface supporting custom dense vector implementations.
- Full metadata preservation (source_file, section, page, last_modified).
- Persistence and automatic re-indexing capabilities.
"""

import os
import re
import math
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from .ingestion import DocumentChunk, ingest_document
from .. import config

# Basic common English stopwords for clean tokenization
ENGLISH_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours"
}

def tokenize(text: str) -> List[str]:
    """Extracts alphanumeric word tokens, lowercased, filtering stopwords."""
    words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
    return [w for w in words if w not in ENGLISH_STOPWORDS]

class RetrievalResult:
    def __init__(self, chunk: DocumentChunk, score: float):
        self.chunk = chunk
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "score": round(self.score, 4)
        }

class LocalTFIDFRetriever:
    """
    High-performance, maintainable local TF-IDF retriever with BM25-style document
    frequency smoothing and section-title boosting.
    """
    def __init__(self,
                 docs_dir: Optional[Path] = None,
                 index_dir: Optional[Path] = None):
        self.docs_dir = Path(docs_dir) if docs_dir else config.KNOWLEDGE_BASE_DIR
        self.index_dir = Path(index_dir) if index_dir else config.INDEX_STORAGE_DIR
        self.chunks: List[DocumentChunk] = []
        self.chunk_map: Dict[str, DocumentChunk] = {}
        self.inverted_index: Dict[str, List[Tuple[int, float]]] = {} # term -> [(chunk_idx, tf)]
        self.idf: Dict[str, float] = {}
        self.chunk_norms: List[float] = []
        self.indexed_files: Dict[str, float] = {} # filename -> mtime
        self.is_indexed = False

    def _compute_vectors(self, chunks: List[DocumentChunk]) -> None:
        """
        Computes TF-IDF inverted index and document norms for the given chunks.
        Applies a 1.5x multiplier to title terms while preserving normal body-term counts.
        Resets index state on empty input.
        """
        num_chunks = len(chunks)
        if num_chunks == 0:
            self.inverted_index = {}
            self.idf = {}
            self.chunk_norms = []
            return

        doc_freq: Dict[str, int] = {}
        chunk_tfs: List[Dict[str, float]] = []

        for chunk in chunks:
            tf_dict: Dict[str, float] = {}
            body_tokens = tokenize(chunk.text)
            title_tokens = tokenize(chunk.section_title)

            # Preserve normal body-term counts
            for t in body_tokens:
                tf_dict[t] = tf_dict.get(t, 0.0) + 1.0

            # Title terms receive a 1.5x multiplier
            for t in title_tokens:
                tf_dict[t] = tf_dict.get(t, 0.0) + 1.0
            for t in set(title_tokens):
                tf_dict[t] *= 1.5

            chunk_tfs.append(tf_dict)
            for term in tf_dict.keys():
                doc_freq[term] = doc_freq.get(term, 0) + 1

        self.idf = {t: math.log(1.0 + (num_chunks - df + 0.5) / (df + 0.5)) + 0.01 for t, df in doc_freq.items()}
        self.inverted_index = {}
        self.chunk_norms = [0.0] * num_chunks

        for c_idx, tf_dict in enumerate(chunk_tfs):
            sum_sq = 0.0
            for term, count in tf_dict.items():
                tfidf_val = (1.0 + math.log(count)) * self.idf.get(term, 0.0)
                sum_sq += tfidf_val * tfidf_val
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append((c_idx, tfidf_val))
            self.chunk_norms[c_idx] = math.sqrt(sum_sq) if sum_sq > 0 else 1.0

    def build_index(self, force: bool = False) -> int:
        """
        Scans docs_dir, parses all supported files, chunks them, and builds TF-IDF index.
        """
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        found_files = []
        for ext in ["*.md", "*.txt", "*.pdf"]:
            found_files.extend(list(self.docs_dir.glob(ext)))

        self.chunks = []
        self.chunk_map = {}
        self.indexed_files = {}

        for fpath in sorted(found_files):
            try:
                doc_chunks = ingest_document(fpath,
                                             chunk_size=config.RAG_CHUNK_SIZE,
                                             chunk_overlap=config.RAG_CHUNK_OVERLAP)
                for chunk in doc_chunks:
                    self.chunks.append(chunk)
                    self.chunk_map[chunk.chunk_id] = chunk
                self.indexed_files[fpath.name] = fpath.stat().st_mtime
            except Exception as e:
                print(f"[RAG] Warning: Failed to ingest {fpath.name}: {e}")

        self._compute_vectors(self.chunks)
        self.is_indexed = True
        self.save_index()
        return len(self.chunks)

    def save_index(self) -> None:
        """Persists chunks and index metadata to JSON files."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        chunks_file = self.index_dir / "chunks.json"
        meta_file = self.index_dir / "index_manifest.json"

        chunks_data = [c.to_dict() for c in self.chunks]
        with open(chunks_file, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, indent=2)

        meta_data = {
            "total_chunks": len(self.chunks),
            "indexed_files": self.indexed_files,
            "vocabulary_size": len(self.idf)
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)

    def load_index(self) -> bool:
        """Loads index from disk if existing and valid."""
        chunks_file = self.index_dir / "chunks.json"
        meta_file = self.index_dir / "index_manifest.json"

        if not chunks_file.exists() or not meta_file.exists():
            return False

        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                raw_chunks = json.load(f)
            self.chunks = [DocumentChunk.from_dict(d) for d in raw_chunks]
            self.chunk_map = {c.chunk_id: c for c in self.chunks}

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.indexed_files = meta.get("indexed_files", {})

            # Rebuild inverted index using helper (resets state if chunks is empty)
            self._compute_vectors(self.chunks)
            self.is_indexed = True
            return True
        except Exception as e:
            print(f"[RAG] Error loading cached index: {e}. Rebuilding...")
            return False


    def retrieve(self, query: str, top_k: Optional[int] = None, min_score: Optional[float] = None) -> List[RetrievalResult]:
        """
        Retrieves top-k relevant chunks matching query, ordered by relevance.
        """
        if not self.is_indexed:
            self.build_index()

        k = top_k or config.RAG_TOP_K
        threshold = min_score if min_score is not None else config.RAG_MIN_SIMILARITY_SCORE

        query_tokens = tokenize(query)
        if not query_tokens or len(self.chunks) == 0:
            return []

        # Calculate query vector TF-IDF
        q_tf: Dict[str, float] = {}
        for t in query_tokens:
            q_tf[t] = q_tf.get(t, 0.0) + 1.0

        q_vec: Dict[str, float] = {}
        q_sum_sq = 0.0
        for t, count in q_tf.items():
            if t in self.idf:
                val = (1.0 + math.log(count)) * self.idf[t]
                q_vec[t] = val
                q_sum_sq += val * val

        q_norm = math.sqrt(q_sum_sq)
        if q_norm == 0.0:
            return []

        # Accumulate dot product scores across chunks using inverted index
        scores: Dict[int, float] = {}
        for term, q_val in q_vec.items():
            if term in self.inverted_index:
                for c_idx, doc_tfidf in self.inverted_index[term]:
                    scores[c_idx] = scores.get(c_idx, 0.0) + (q_val * doc_tfidf)

        # Normalize by chunk L2 norms for cosine similarity
        results = []
        for c_idx, dot_prod in scores.items():
            cos_sim = dot_prod / (q_norm * self.chunk_norms[c_idx])
            if cos_sim >= threshold:
                results.append(RetrievalResult(chunk=self.chunks[c_idx], score=cos_sim))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]

