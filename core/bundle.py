# -*- coding: utf-8 -*-
"""OpenMemory - Memory Bundle Import/Export & Markdown Vault Serializer."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from core.engine import GovernanceEngine
from core.models import Memory


class MemoryBundle:
    VERSION = "2.0"

    @classmethod
    def export_json(cls, engine: GovernanceEngine, out_file: Path) -> int:
        """导出全量记忆、审计日志与画像为单个轻量独立 JSON 文件."""
        out_file = Path(out_file).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        mems = engine.get_memories(include_inactive=True, limit=100000)
        logs = engine.get_audit_logs(limit=100000)
        stats = engine.get_stats()

        bundle = {
            "openmemory_version": cls.VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": stats,
            "memories": [m.to_dict() for m in mems],
            "audit_logs": [l.to_dict() for l in logs]
        }

        out_file.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(mems)

    @classmethod
    def export_markdown_vault(cls, engine: GovernanceEngine, out_dir: Path) -> int:
        """导出为 Git / Obsidian 友好的纯文本 Markdown Vault (每个记忆独立文档带 YAML 头部)."""
        out_dir = Path(out_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        mems = engine.get_memories(include_inactive=True, limit=100000)
        count = 0

        for m in mems:
            cat_dir = out_dir / m.category
            cat_dir.mkdir(parents=True, exist_ok=True)

            md_path = cat_dir / f"{m.id}.md"
            lines = [
                "---",
                f"id: \"{m.id}\"",
                f"category: \"{m.category}\"",
                f"confidence: {m.confidence}",
                f"status: \"{m.status}\"",
                f"source_type: \"{m.source_type}\"",
                f"sensitivity: \"{m.sensitivity}\"",
                f"scope: \"{m.scope}\"",
                f"source_client: \"{m.source_client}\"",
                f"source_agent: \"{m.source_agent}\"",
                f"source_session: \"{m.source_session}\"",
                f"reinforced_count: {m.reinforced_count}",
                f"created_at: \"{m.created_at}\"",
                f"updated_at: \"{m.updated_at}\"",
                "---",
                "",
                f"# {m.statement}",
                ""
            ]

            if m.source_snippet:
                lines.extend([
                    "> **原始事实/用户原话证据**:",
                    f"> {m.source_snippet}",
                    ""
                ])

            if m.superseded_by:
                lines.append(f"↳ **已被取代为**: `{m.superseded_by}`\n")
            if m.supersedes_id:
                lines.append(f"↳ **历史指回演进自**: `{m.supersedes_id}`\n")

            md_path.write_text("\n".join(lines), encoding="utf-8")
            count += 1

        # 生成根目录 INDEX.md
        index_lines = [
            "# 🧠 OpenMemory Markdown Vault Index",
            f"> 导出时间: {datetime.now(timezone.utc).isoformat(timespec='seconds')} | 记忆条目: {count}",
            "",
            "| ID | 类别 | 来源类型 | 授权级别 | 状态 | 记忆陈述 |",
            "|---|---|---|---|---|---|"
        ]
        for m in mems:
            rel = f"{m.category}/{m.id}.md"
            stmt = m.statement.replace("|", "/")[:50]
            index_lines.append(f"| [{m.id}]({rel}) | {m.category} | {m.source_type} | {m.sensitivity} | {m.status} | {stmt} |")

        (out_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8")
        return count

    @classmethod
    def import_bundle(cls, engine: GovernanceEngine, in_path: Path) -> int:
        """从 JSON 备份文件或 Markdown Vault 目录导入记忆 (幂等去重)."""
        in_path = Path(in_path).resolve()
        if not in_path.exists():
            raise FileNotFoundError(f"{in_path} does not exist")

        conn = engine.storage.get_connection()
        count = 0
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

        try:
            if in_path.is_file():
                # JSON 文件
                data = json.loads(in_path.read_text(encoding="utf-8"))
                memories = data.get("memories", [])
                for item in memories:
                    m = Memory.from_dict(item)
                    conn.execute("""
                        INSERT INTO memories (id, category, statement, confidence, status, source_type,
                                             sensitivity, scope, source_client, source_agent, source_session,
                                             source_snippet, superseded_by, supersedes_id, reinforced_count,
                                             last_reinforced_at, derived_from, conflict_with, grace_until,
                                             created_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET
                        statement=excluded.statement, confidence=excluded.confidence, status=excluded.status,
                        reinforced_count=excluded.reinforced_count, updated_at=excluded.updated_at
                    """, (
                        m.id, m.category, m.statement, m.confidence, m.status, m.source_type,
                        m.sensitivity, m.scope, m.source_client, m.source_agent, m.source_session,
                        m.source_snippet, m.superseded_by, m.supersedes_id, m.reinforced_count,
                        m.last_reinforced_at, m.derived_from, m.conflict_with, m.grace_until,
                        m.created_at or now_iso, m.updated_at or now_iso
                    ))
                    count += 1
            elif in_path.is_dir():
                # Markdown Vault 目录
                for md_file in in_path.rglob("*.md"):
                    if md_file.name in ("README.md", "INDEX.md"):
                        continue
                    text = md_file.read_text(encoding="utf-8")
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            yaml_text = parts[1]
                            body = parts[2].strip()
                            # 简易解析 yaml 字段
                            meta = {}
                            for line in yaml_text.splitlines():
                                if ":" in line:
                                    k, v = line.split(":", 1)
                                    meta[k.strip()] = v.strip().strip('"\'')
                            mid = meta.get("id") or md_file.stem
                            stmt = body.split("\n", 1)[0].removeprefix("#").strip() if body else mid
                            cat = meta.get("category", "preference")
                            stype = meta.get("source_type", "direct_statement")
                            sens = meta.get("sensitivity", "L1")
                            scope = meta.get("scope", "general")
                            stat = meta.get("status", "active")

                            conn.execute("""
                                INSERT OR REPLACE INTO memories(id, category, statement, confidence, status,
                                                               source_type, sensitivity, scope, source_client,
                                                               source_agent, source_session, created_at, updated_at)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """, (mid, cat, stmt, float(meta.get("confidence", 1.0)), stat, stype, sens, scope,
                                  meta.get("source_client", "import"), meta.get("source_agent", "manual"),
                                  meta.get("source_session", "vault_import"), now_iso, now_iso))
                            count += 1
            conn.commit()
            return count
        finally:
            conn.close()
