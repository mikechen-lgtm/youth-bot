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

from openai_service import (
    OPENAI_CLIENT,
    create_rag_store,
    upload_file_to_rag_store,
    delete_rag_store,
)


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
            if existing.startswith(f"{key}=") or existing.startswith(f"#{key}="):
                lines[i] = line
                updated = True
                break
        if not updated:
            lines.append(line)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(line + "\n", encoding="utf-8")


def _get_existing_files(store_id: str) -> dict[str, str]:
    """Get existing files in vector store. Returns {filename: file_id}."""
    client = OPENAI_CLIENT
    if not client:
        return {}

    try:
        files = client.vector_stores.files.list(vector_store_id=store_id)
        result = {}
        for f in files.data:
            try:
                file_info = client.files.retrieve(f.id)
                result[file_info.filename] = f.id
            except Exception:
                pass
        return result
    except Exception as e:
        print(f"Warning: Could not list existing files: {e}", file=sys.stderr)
        return {}


def _delete_file_from_store(store_id: str, file_id: str) -> None:
    """Delete a file from vector store."""
    client = OPENAI_CLIENT
    if not client:
        return

    try:
        client.vector_stores.files.delete(vector_store_id=store_id, file_id=file_id)
        client.files.delete(file_id)
    except Exception as e:
        print(f"Warning: Could not delete file {file_id}: {e}", file=sys.stderr)


def rebuild_store(name: str, data_dir: Path, env_path: Path) -> str:
    """
    Mode 1: 完全重建
    - 刪除現有 vector store（如果存在）
    - 建立新的 vector store
    - 上傳所有檔案
    - 更新 .env
    """
    # 檢查是否有現有的 store ID
    old_store_id = os.getenv("RAG_VECTOR_STORE_ID")

    if old_store_id:
        print(f"Deleting existing vector store: {old_store_id}")
        try:
            delete_rag_store(old_store_id)
            print(f"  ✓ Deleted")
        except Exception as e:
            print(f"  ⚠ Could not delete (may not exist): {e}")

    # 建立新的 store
    print(f"\nCreating new vector store: {name}")
    store_id = create_rag_store(name)
    print(f"  ✓ Created: {store_id}")

    # 上傳所有檔案
    files = _collect_files(data_dir)
    print(f"\nUploading {len(files)} files:")
    for file_path in files:
        print(f"  Uploading {file_path.name}...", end=" ", flush=True)
        upload_file_to_rag_store(store_id, str(file_path))
        print("✓")

    # 更新 .env
    _write_env_var(env_path, "RAG_VECTOR_STORE_ID", store_id)
    print(f"\n✓ Updated {env_path} with RAG_VECTOR_STORE_ID={store_id}")

    return store_id


def update_store(data_dir: Path) -> str:
    """
    Mode 2: 增量更新
    - 使用現有的 RAG_VECTOR_STORE_ID
    - 比對本地檔案與遠端檔案
    - 只上傳新增或修改的檔案
    """
    store_id = os.getenv("RAG_VECTOR_STORE_ID")
    if not store_id:
        print("Error: RAG_VECTOR_STORE_ID not found in environment.", file=sys.stderr)
        print("Use --rebuild mode to create a new vector store first.", file=sys.stderr)
        sys.exit(1)

    print(f"Using existing vector store: {store_id}")

    # 取得現有檔案列表
    existing_files = _get_existing_files(store_id)
    print(f"  Existing files: {len(existing_files)}")
    for name in existing_files:
        print(f"    - {name}")

    # 取得本地檔案
    local_files = _collect_files(data_dir)
    local_filenames = {f.name for f in local_files}

    # 找出需要上傳的新檔案
    new_files = [f for f in local_files if f.name not in existing_files]

    # 找出需要刪除的檔案（遠端有但本地沒有）
    deleted_files = {name: fid for name, fid in existing_files.items() if name not in local_filenames}

    print(f"\nChanges detected:")
    print(f"  - New files to upload: {len(new_files)}")
    print(f"  - Files to remove: {len(deleted_files)}")

    # 刪除不再需要的檔案
    if deleted_files:
        print(f"\nRemoving {len(deleted_files)} files:")
        for name, fid in deleted_files.items():
            print(f"  Removing {name}...", end=" ", flush=True)
            _delete_file_from_store(store_id, fid)
            print("✓")

    # 上傳新檔案
    if new_files:
        print(f"\nUploading {len(new_files)} new files:")
        for file_path in new_files:
            print(f"  Uploading {file_path.name}...", end=" ", flush=True)
            upload_file_to_rag_store(store_id, str(file_path))
            print("✓")

    if not new_files and not deleted_files:
        print("\n✓ No changes needed. Vector store is up to date.")
    else:
        print(f"\n✓ Update complete.")

    return store_id


def list_store(store_id: str = None) -> None:
    """列出 vector store 中的所有檔案"""
    store_id = store_id or os.getenv("RAG_VECTOR_STORE_ID")
    if not store_id:
        print("Error: No vector store ID provided.", file=sys.stderr)
        sys.exit(1)

    print(f"Vector Store: {store_id}")
    existing_files = _get_existing_files(store_id)

    if not existing_files:
        print("  (empty)")
    else:
        print(f"  Files ({len(existing_files)}):")
        for name, fid in existing_files.items():
            print(f"    - {name} ({fid})")


def main() -> int:
    load_dotenv()
    load_dotenv(".env.local")

    parser = argparse.ArgumentParser(
        description="Manage OpenAI File Search vector store for RAG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 完全重建（刪除舊的，建立新的，更新 .env）
  python scripts/bootstrap_vector_store.py --rebuild

  # 增量更新（使用現有 store，只上傳新檔案）
  python scripts/bootstrap_vector_store.py --update

  # 列出現有檔案
  python scripts/bootstrap_vector_store.py --list

  # 指定資料目錄
  python scripts/bootstrap_vector_store.py --rebuild --data-dir ./my_data
        """
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--rebuild",
        action="store_true",
        help="完全重建：刪除現有 store，建立新的，上傳所有檔案，更新 .env",
    )
    mode_group.add_argument(
        "--update",
        action="store_true",
        help="增量更新：使用現有 store，只上傳新增的檔案",
    )
    mode_group.add_argument(
        "--list",
        action="store_true",
        help="列出現有 vector store 中的檔案",
    )

    parser.add_argument(
        "--name",
        default="TaoyuanYouthBureauKB",
        help="Vector store display name (for --rebuild).",
    )
    parser.add_argument(
        "--data-dir",
        default=os.getenv("RAG_DATA_DIR", "rag_data"),
        help="Directory containing files to upload.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Env file path to update (for --rebuild).",
    )

    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Missing OPENAI_API_KEY in environment.", file=sys.stderr)
        return 1

    data_dir = Path(args.data_dir)

    if args.list:
        list_store()
        return 0

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        return 1

    files = _collect_files(data_dir)
    if not files:
        print(f"Error: No supported files found in {data_dir}", file=sys.stderr)
        return 1

    print(f"Data directory: {data_dir}")
    print(f"Local files: {len(files)}")
    for f in files:
        print(f"  - {f.name}")
    print()

    if args.rebuild:
        rebuild_store(args.name, data_dir, Path(args.env_file))
    elif args.update:
        update_store(data_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
