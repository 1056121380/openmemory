"""Memory Export and Import CLI Tool.

Supports exporting your entire memory store to:
1. Portable JSON Bundle (.json)
2. Git/Obsidian Markdown Vault (.md with YAML frontmatter)
And importing bundles into any OpenMemory database.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.bundle import MemoryBundle
from core.storage import SQLiteStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("openmemory.bundle")


def main():
    parser = argparse.ArgumentParser(description="OpenMemory Export and Import Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export memories to JSON bundle or Markdown vault")
    export_parser.add_argument("--format", choices=["json", "vault"], default="vault", help="Export format: 'vault' (Markdown) or 'json'")
    export_parser.add_argument("--output", "-o", required=True, help="Output file path (for json) or directory path (for vault)")
    export_parser.add_argument("--db", default=None, help="Path to SQLite memory database")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import memories from JSON bundle")
    import_parser.add_argument("--file", "-f", required=True, help="Path to JSON bundle file")
    import_parser.add_argument("--db", default=None, help="Path to SQLite memory database")
    import_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing memory records")

    args = parser.parse_args()
    storage = SQLiteStorage(db_path=args.db)

    if args.command == "export":
        if args.format == "json":
            out_path = MemoryBundle.export_json(storage, args.output)
            logger.info(f"Successfully exported JSON bundle to: {out_path}")
        else:
            out_dir = MemoryBundle.export_markdown_vault(storage, args.output)
            logger.info(f"Successfully generated Markdown Vault at: {out_dir}")

    elif args.command == "import":
        stats = MemoryBundle.import_bundle(storage, args.file, overwrite=args.overwrite)
        logger.info(f"Import complete: imported={stats['imported']}, skipped={stats['skipped']}")


if __name__ == "__main__":
    main()
