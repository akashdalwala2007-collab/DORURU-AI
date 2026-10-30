#!/usr/bin/env python3
"""
scripts/reindex_knowledge_base.py - Standalone Knowledge Base Re-Indexing Utility

Allows adding, updating, or removing college documents without changing any application code.
Usage:
    python scripts/reindex_knowledge_base.py [--force] [--docs-dir PATH] [--index-dir PATH]
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.rag.retriever import LocalTFIDFRetriever
from backend.app import config

def main():
    parser = argparse.ArgumentParser(description="Re-index DORURU College Knowledge Base documents.")
    parser.add_argument("--docs-dir", type=str, default=str(config.KNOWLEDGE_BASE_DIR),
                        help="Path to folder containing documents (.md, .txt, .pdf)")
    parser.add_argument("--index-dir", type=str, default=str(config.INDEX_STORAGE_DIR),
                        help="Path to folder where chunk index is saved")
    parser.add_argument("--force", action="store_true",
                        help="Force full rebuild of index from scratch")

    args = parser.parse_args()

    docs_path = Path(args.docs_dir)
    index_path = Path(args.index_dir)

    print("==================================================")
    print("  DORURU College Knowledge Base Re-Indexer        ")
    print("==================================================")
    print(f"Documents Directory: {docs_path}")
    print(f"Index Directory:     {index_path}")
    print(f"Force Rebuild:       {args.force}")
    print("--------------------------------------------------")

    if not docs_path.exists():
        print(f"Error: Documents directory '{docs_path}' does not exist.")
        sys.exit(1)

    retriever = LocalTFIDFRetriever(docs_dir=docs_path, index_dir=index_path)
    total_chunks = retriever.build_index(force=args.force)

    print(f"Re-indexing complete!")
    print(f"Files Indexed:   {len(retriever.indexed_files)}")
    for fname in retriever.indexed_files.keys():
        print(f"  - {fname}")
    print(f"Total Chunks:    {total_chunks}")
    print(f"Vocabulary Size: {len(retriever.idf)} terms")
    print(f"Manifest Saved:  {index_path / 'index_manifest.json'}")
    print("==================================================")

if __name__ == "__main__":
    main()

