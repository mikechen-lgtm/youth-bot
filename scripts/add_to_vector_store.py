"""Add new files to an existing OpenAI File Search vector store."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai_service import upload_file_to_rag_store


def _collect_files(root: Path, exts: set[str]) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in exts)


def main() -> int:
    load_dotenv()
    load_dotenv(".env.local")

    parser = argparse.ArgumentParser(
        description="Upload additional files to an existing vector store."
    )
    parser.add_argument(
        "--store-id",
        default=os.getenv("RAG_VECTOR_STORE_ID") or os.getenv("RAG_STORE_NAME"),
        help="Vector store id (defaults to RAG_VECTOR_STORE_ID).",
    )
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        default=[],
        help="File path to upload (repeatable).",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory containing files to upload.",
    )
    parser.add_argument(
        "--exts",
        default=".md,.txt,.pdf,.html,.json",
        help="Comma-separated file extensions to include when using --data-dir.",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY in environment.", file=sys.stderr)
        return 1

    if not args.store_id:
        print("Missing vector store id. Set RAG_VECTOR_STORE_ID or use --store-id.", file=sys.stderr)
        return 1

    exts = {ext.strip().lower() for ext in args.exts.split(",") if ext.strip()}
    upload_queue: list[Path] = []

    for file_path in args.files:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            return 1
        upload_queue.append(path)

    if args.data_dir:
        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            print(f"Data directory not found: {data_dir}", file=sys.stderr)
            return 1
        upload_queue.extend(_collect_files(data_dir, exts))

    if not upload_queue:
        print("No files selected. Use --file or --data-dir.", file=sys.stderr)
        return 1

    for file_path in upload_queue:
        upload_file_to_rag_store(args.store_id, str(file_path))

    print(f"Uploaded {len(upload_queue)} file(s) to {args.store_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
