"""Local Session Scrubber & Ingestion Tool for OpenMemory.

Scans local conversation logs, scrubs sensitive secrets/IPs/tokens using
strict regex rules, and syncs sanitized memories to OpenMemory (Local or Remote).
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.engine import GovernanceEngine
from core.models import Sensitivity, SourceType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("openmemory.sync")

# Privacy scrubbing rules
SECRET_PATTERNS = [
    # Standard OpenAI / MiniMax / Anthropic / GitHub keys
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}", re.IGNORECASE), "<REDACTED_API_KEY>"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}", re.IGNORECASE), "<REDACTED_GITHUB_TOKEN>"),
    (re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{15,})", re.IGNORECASE), "Bearer <REDACTED_TOKEN>"),
    # Private / Local IPv4 addresses
    (re.compile(r"\b(192\.168\.\d{1,3}\.\d{1,3})\b"), "<REDACTED_LOCAL_IP>"),
    (re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"), "<REDACTED_PRIVATE_IP>"),
    (re.compile(r"\b(172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})\b"), "<REDACTED_PRIVATE_IP>"),
    (re.compile(r"\b(100\.(?:6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d{1,3}\.\d{1,3})\b"), "<REDACTED_CGNAT_IP>"),
    # Passwords in URLs / connection strings
    (re.compile(r"://([^:\s]+):([^@\s]+)@"), r"://\1:<REDACTED_PASSWORD>@"),
    # Windows User names in standard paths: C:\Users\<username>\
    (re.compile(r"([A-Za-z]:[\\/]Users[\\/])([^\\/]+)", re.IGNORECASE), r"\1<USER>"),
]


def scrub_sensitive_data(text: str) -> str:
    """Apply all privacy scrubbing rules to prevent secrets or private IDs from leaking."""
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class SessionSync:
    """Collects and sanitizes session transcripts and records them into OpenMemory."""

    def __init__(self, mode: str = "local", db_path: Optional[str] = None):
        self.mode = mode
        self.engine = GovernanceEngine(db_path=db_path) if mode == "local" else None

    def sync_file(self, file_path: str, topic: str = "session_sync") -> int:
        """Read a file, scrub sensitive information, and extract bullet memory points."""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0

        raw_content = path.read_text(encoding="utf-8", errors="ignore")
        clean_content = scrub_sensitive_data(raw_content)

        count = 0
        # If the file is JSONL (e.g. transcript logs)
        if path.suffix == ".jsonl":
            for line in clean_content.splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    # Extract user prompt or assistant decisions
                    text = record.get("content") or record.get("text") or ""
                    if text and len(text.strip()) > 15:
                        self._record_candidate(topic, text, source_ref=f"{path.name}#log")
                        count += 1
                except Exception:
                    continue
        else:
            # Markdown or text file: treat paragraphs or bullet points as candidate items
            lines = clean_content.splitlines()
            for line in lines:
                stripped = line.strip()
                if (stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("1. ")) and len(stripped) > 20:
                    summary = stripped.lstrip("-*0123456789. ")
                    self._record_candidate(topic, summary, source_ref=path.name)
                    count += 1

        logger.info(f"Synchronized {count} sanitized entries from {path.name}")
        return count

    def _record_candidate(self, topic: str, summary: str, source_ref: str):
        if self.engine:
            self.engine.add_memory(
                topic=topic,
                summary=summary,
                source_type=SourceType.USER_STATEMENT,
                source_ref=source_ref,
                confidence=0.85,
                sensitivity=Sensitivity.L1_WORK,
                auto_supersede=True,
            )


def main():
    parser = argparse.ArgumentParser(description="Sanitize and sync local transcripts to OpenMemory")
    parser.add_argument("path", help="Path to transcript file or directory of logs")
    parser.add_argument("--topic", default="session_log", help="Topic tag for ingested items")
    parser.add_argument("--db", default=None, help="Path to SQLite memory database")
    args = parser.parse_args()

    sync = SessionSync(mode="local", db_path=args.db)
    target = Path(args.path)

    if target.is_file():
        sync.sync_file(str(target), topic=args.topic)
    elif target.is_dir():
        for ext in ("*.jsonl", "*.md", "*.txt"):
            for f in target.glob(ext):
                sync.sync_file(str(f), topic=args.topic)
    else:
        logger.error(f"Path does not exist: {target}")


if __name__ == "__main__":
    main()
