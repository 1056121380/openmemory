"""LLM-driven Memory Digest Worker.

Periodically digests raw sessions or text logs into structured memories
with provenance, initial confidence, and sensitivity tiers.
Works with any OpenAI-compatible API (OpenAI, DeepSeek, Ollama, vLLM, MiniMax, etc.).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from core.engine import GovernanceEngine
from core.models import Sensitivity, SourceType

logger = logging.getLogger("openmemory.digest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DIGEST_SYSTEM_PROMPT = """You are an Enterprise Memory Governance and Knowledge Distillation Engine.
Your task is to analyze conversational transcripts or work logs and extract high-value personal memories, preferences, technical decisions, and behavioral habits.

Strict Governance Rules:
1. Distinguish Source Type rigorously:
   - "user_statement": Facts or preferences explicitly declared by the user (e.g. "I prefer dark mode", "Never use semicolons in Python"). Initial confidence: 0.95.
   - "ai_inference": Inferred patterns, traits, or deductions made by observing behavior (e.g. "User seems to write async code often"). Initial confidence: 0.65.
   - "tool_event": Direct execution outcomes or tool facts. Initial confidence: 0.85.
2. Sensitivity Tiering:
   - "L0_public": Generic preferences, style habits, tool choices (e.g. "prefers pytest over unittest").
   - "L1_work": Project architecture decisions, internal stack details, workflows.
   - "L2_private": Strictly personal details, private schedules, or sensitive habits.
3. Provenance & Evidence:
   - Provide a concise `source_ref` describing the context.
   - Attach literal `evidence` (the user's exact quote or key event line).
4. Memory Format:
   - Topic: short canonical label (e.g. "code_style", "database_choice", "ui_preference").
   - Summary: clear, atomic, actionable statement.
   - Tags: 2-5 relevant keywords.

Output ONLY a JSON array of memory objects:
[
  {
    "topic": "code_style",
    "summary": "Strictly use Ruff and Black for Python formatting",
    "source_type": "user_statement",
    "confidence": 0.95,
    "sensitivity": "L0_public",
    "scope": "global",
    "evidence": "User said: Please configure Ruff and Black in all future repos",
    "tags": ["python", "linter", "formatter"]
  }
]
If there are no valuable long-term memories to extract, output an empty JSON array: [].
"""


class DigestWorker:
    """Extracts structured memories from text or raw sessions using an LLM."""

    def __init__(
        self,
        engine: GovernanceEngine,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.engine = engine
        self.api_base = (
            api_base
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def call_llm(self, prompt: str) -> str:
        """Call standard OpenAI-compatible chat completion endpoint via stdlib urllib."""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                res_body = response.read().decode("utf-8")
                data = json.loads(res_body)
                content = data["choices"][0]["message"]["content"].strip()
                # Clean markdown backticks if wrapped
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return content.strip()
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            logger.error(f"LLM API HTTPError {e.code}: {err_msg}")
            raise RuntimeError(f"LLM API request failed: HTTP {e.code} - {err_msg}")
        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            raise

    def digest_text(self, text: str, source_ref: str = "text_digest") -> List[Dict[str, Any]]:
        """Digest a block of text into structured memories and commit them."""
        if not text or len(text.strip()) < 10:
            return []

        user_prompt = f"Analyze the following session/text and extract persistent memories:\n\n---\n{text}\n---"
        raw_json = self.call_llm(user_prompt)

        try:
            items = json.loads(raw_json)
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON: {e}\nRaw content: {raw_json[:300]}")
            return []

        committed = []
        for item in items:
            topic = item.get("topic", "general")
            summary = item.get("summary", "")
            if not summary:
                continue

            src_type_str = item.get("source_type", "ai_inference")
            try:
                src_type = SourceType(src_type_str)
            except ValueError:
                src_type = SourceType.AI_INFERENCE

            sens_str = item.get("sensitivity", "L1_work")
            try:
                sens = Sensitivity(sens_str)
            except ValueError:
                sens = Sensitivity.L1_WORK

            confidence = float(item.get("confidence", 0.7))
            scope = item.get("scope", "global")
            evidence = item.get("evidence", "")
            tags = item.get("tags", [])

            mem = self.engine.add_memory(
                topic=topic,
                summary=summary,
                source_type=src_type,
                source_ref=source_ref,
                confidence=confidence,
                sensitivity=sens,
                scope=scope,
                evidence=evidence,
                tags=tags,
                auto_supersede=True,
            )
            committed.append(mem.to_dict())

        logger.info(f"Successfully digested {len(committed)} memories from '{source_ref}'.")
        return committed


def main():
    """CLI runner for standalone digest testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Memory Digest Worker")
    parser.add_argument("--file", help="Path to text or log file to digest")
    parser.add_argument("--db", default=None, help="Path to memory.db SQLite database")
    args = parser.parse_args()

    engine = GovernanceEngine(db_path=args.db)
    worker = DigestWorker(engine=engine)

    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        res = worker.digest_text(content, source_ref=os.path.basename(args.file))
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("Usage: python -m server.digest_worker --file /path/to/log.txt")


if __name__ == "__main__":
    main()
