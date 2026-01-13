"""Bootstrap an OpenAI File Search vector store from local rag_data."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai_service import create_rag_store, upload_file_to_rag_store


def _collect_files(root: Path) -> list[Path]:
    exts = {".md", ".txt", ".pdf", ".html", ".json"}
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in exts)


def _write_env_var(env_path: Path, key: str, value: str) -> None:
    line = f"{key}={value}"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        updated = False
        for i, existing in enumerate(lines):
            if existing.startswith(f"{key}="):
                lines[i] = line
                updated = True
                break
        if not updated:
            lines.append(line)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(line + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv()
    load_dotenv(".env.local")
    parser = argparse.ArgumentParser(
        description="Create a vector store and upload rag_data files."
    )
    parser.add_argument(
        "--name",
        default="TaoyuanYouthBureauKB",
        help="Vector store display name.",
    )
    parser.add_argument(
        "--data-dir",
        default=os.getenv("RAG_DATA_DIR", "rag_data"),
        help="Directory containing files to upload.",
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Write RAG_VECTOR_STORE_ID to .env (or --env-file).",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Env file path to update when --write-env is set.",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Missing OPENAI_API_KEY in environment.", file=sys.stderr)
        return 1

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}", file=sys.stderr)
        return 1

    files = _collect_files(data_dir)
    if not files:
        print(f"No supported files found in {data_dir}", file=sys.stderr)
        return 1

    store_id = create_rag_store(args.name)
    for file_path in files:
        upload_file_to_rag_store(store_id, str(file_path))

    print(f"RAG_VECTOR_STORE_ID={store_id}")

    if args.write_env:
        env_path = Path(args.env_file)
        _write_env_var(env_path, "RAG_VECTOR_STORE_ID", store_id)
        print(f"Updated {env_path} with RAG_VECTOR_STORE_ID.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
