# -*- coding: utf-8 -*-
"""OpenMemory - SQLite Storage Engine (WAL Mode + FTS5 Full Text Index)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any


def get_default_data_dir() -> Path:
    """获取默认数据存储目录 (优先环境变量 > 用户目录 ~/.openmemory)."""
    env_dir = os.environ.get("OPENMEMORY_DATA_DIR", "").strip()
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
    else:
        p = Path.home() / ".openmemory"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Storage:
    def __init__(self, db_path: Optional[Path | str] = None):
        if db_path is None:
            self.db_path = get_default_data_dir() / "memory.db"
        else:
            self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        conn = self.get_connection()
        try:
            # 1. 核心记忆表 (Memories)
            conn.execute("""CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                category TEXT DEFAULT 'preference',
                statement TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                status TEXT DEFAULT 'active',
                source_type TEXT DEFAULT 'direct_statement',
                sensitivity TEXT DEFAULT 'L1',
                scope TEXT DEFAULT 'general',
                source_client TEXT DEFAULT 'local',
                source_agent TEXT DEFAULT 'manual',
                source_session TEXT DEFAULT 'manual_entry',
                source_snippet TEXT DEFAULT '',
                superseded_by TEXT DEFAULT '',
                supersedes_id TEXT DEFAULT '',
                reinforced_count INTEGER DEFAULT 1,
                last_reinforced_at TEXT DEFAULT '',
                derived_from TEXT DEFAULT '',
                conflict_with TEXT DEFAULT '',
                grace_until TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )""")

            # 2. 变更审计流水 (Audit Logs)
            conn.execute("""CREATE TABLE IF NOT EXISTS memory_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT,
                action TEXT,
                old_value TEXT,
                new_value TEXT,
                operator TEXT,
                reason TEXT,
                ts TEXT
            )""")

            # 3. 原始会话全文检索 (FTS5)
            try:
                conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
                    path UNINDEXED, client UNINDEXED, agent UNINDEXED,
                    session_id UNINDEXED, body, tokenize='trigram')""")
            except sqlite3.OperationalError:
                conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
                    path UNINDEXED, client UNINDEXED, agent UNINDEXED,
                    session_id UNINDEXED, body)""")

            conn.execute("CREATE TABLE IF NOT EXISTS fts_state(path TEXT PRIMARY KEY)")

            # 4. 会话便签与结构化提炼
            conn.execute("""CREATE TABLE IF NOT EXISTS session_annotations(
                client TEXT, agent TEXT, session_id TEXT,
                notes TEXT, tags TEXT, updated_at TEXT,
                PRIMARY KEY(client, agent, session_id))""")

            conn.execute("""CREATE TABLE IF NOT EXISTS autodigest(
                client TEXT, agent TEXT, session_id TEXT,
                project TEXT, summary TEXT, created_at TEXT,
                PRIMARY KEY(client, agent, session_id))""")

            # 自动迁移检查（热升级）
            self._migrate(conn)

            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_status ON memories(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_cat ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_sens ON memories(sensitivity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_stype ON memories(source_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_scope ON memories(scope)")
            conn.commit()
        finally:
            conn.close()

    def _migrate(self, conn: sqlite3.Connection):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
        additions = [
            ("source_type", "TEXT DEFAULT 'direct_statement'"),
            ("scope", "TEXT DEFAULT 'general'"),
            ("supersedes_id", "TEXT DEFAULT ''"),
            ("reinforced_count", "INTEGER DEFAULT 1"),
            ("last_reinforced_at", "TEXT DEFAULT ''"),
            ("derived_from", "TEXT DEFAULT ''"),
            ("conflict_with", "TEXT DEFAULT ''"),
            ("grace_until", "TEXT DEFAULT ''"),
        ]
        for cname, ctype in additions:
            if cname not in cols:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {cname} {ctype}")


SQLiteStorage = Storage

