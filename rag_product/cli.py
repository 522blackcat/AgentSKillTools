"""Command line entry point for local RAG training."""

from __future__ import annotations

import argparse
import json

from rag_product.pipeline import RagEngine
from rag_product.validate import build_demo_long_text, run_validation


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG engineering trainer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Load and embed a txt/md file")
    ingest_parser.add_argument("file_path")

    search_parser = subparsers.add_parser("search", help="Search the local vector store")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=None)

    context_parser = subparsers.add_parser(
        "context",
        help="Build retrieval context that can be injected into an agent prompt",
    )
    context_parser.add_argument("query")
    context_parser.add_argument("--top-k", type=int, default=None)

    demo_parser = subparsers.add_parser("demo-long-text", help="Write a synthetic long RAG document")
    demo_parser.add_argument("output_path")

    subparsers.add_parser("validate", help="Run deterministic long-document RAG checks")

    args = parser.parse_args()
    engine = RagEngine()

    if args.command == "ingest":
        print(engine.ingest_file(args.file_path))
    elif args.command == "search":
        context = engine.search(args.query, args.top_k)
        for result in context.results:
            source = result.chunk.metadata.get("source", result.chunk.doc_id)
            print(f"{result.score:.4f} {source}#{result.chunk.chunk_id}")
            print(result.chunk.text[:500].replace("\n", " "))
            print()
    elif args.command == "context":
        print(engine.build_agent_context(args.query, args.top_k))
    elif args.command == "demo-long-text":
        with open(args.output_path, "w", encoding="utf-8") as f:
            f.write(build_demo_long_text())
        print({"path": args.output_path})
    elif args.command == "validate":
        print(json.dumps(run_validation(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
