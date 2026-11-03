# -*- coding: utf-8 -*-
"""OpenMemory - 6-Layer Memory Governance & Provenance Engine."""
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

from core.models import Memory, AuditLog, SourceType, MemoryStatus, Sensitivity, Scope
from core.storage import Storage


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GovernanceEngine:
    """Enterprise 6-Layer Memory Governance Engine."""

    def __init__(self, storage: Optional[Storage] = None, db_path: Optional[str] = None):
        if storage is not None:
            self.storage = storage
        elif db_path is not None:
            self.storage = Storage(db_path=db_path)
        else:
            self.storage = Storage()

    # --------------------------------------------------------------------------
    # 第 3 层：置信度衰减引擎 (Confidence Decay Worker)
    # --------------------------------------------------------------------------
    def apply_confidence_decay(self) -> int:
        """检查所有未被印证的 AI 自主推断，超过14天未印证自动按周衰减，低于阈值(0.40)移入待复核."""
        conn = self.storage.get_connection()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat(timespec="seconds")
        affected = 0
        try:
            rows = conn.execute("""
                SELECT id, confidence, created_at, last_reinforced_at, statement
                FROM memories
                WHERE status = 'active' AND source_type = 'ai_inference'
            """).fetchall()

            for mid, conf, created_at, last_rf, stmt in rows:
                ref_str = last_rf or created_at or now_iso
                try:
                    ref_dt = datetime.fromisoformat(ref_str.replace("Z", "+00:00"))
                    days = (now - ref_dt).days
                except Exception:
                    days = 0

                if days > 14:
                    weeks_over = (days - 14) / 7.0
                    new_conf = max(0.2, round(conf - weeks_over * 0.05, 2))
                    if new_conf != conf:
                        if new_conf < 0.40:
                            # 跌破置信阈值，转入待复核
                            conn.execute(
                                "UPDATE memories SET confidence=?, status='pending_review', updated_at=? WHERE id=?",
                                (new_conf, now_iso, mid)
                            )
                            self._log_audit(
                                conn, mid, "decay_to_review", f"conf={conf}",
                                f"conf={new_conf}, status=pending_review", "system_decay",
                                "推断长期未印证自然衰减，转入人工复核"
                            )
                            affected += 1
                        else:
                            conn.execute("UPDATE memories SET confidence=?, updated_at=? WHERE id=?",
                                         (new_conf, now_iso, mid))
            conn.commit()
            return affected
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 第 4 层：冲突检测引擎 (Conflict Detection)
    # --------------------------------------------------------------------------
    def _detect_conflict(self, conn, category: str, scope: str, statement: str) -> Optional[str]:
        """排查同分类同作用域内是否存在互斥或语义高度重叠但陈述相左的现有记忆."""
        words = [w for w in re.findall(r'[\w]{2,}', statement) if len(w) >= 2]
        if not words:
            return None

        actives = conn.execute(
            "SELECT id, statement FROM memories WHERE category=? AND status IN ('active', 'pinned') AND scope=?",
            (category, scope)
        ).fetchall()

        for e_id, e_stmt in actives:
            overlap = sum(1 for w in words if w.lower() in e_stmt.lower())
            # 关键词重叠显著但陈述不完全一致 -> 疑似冲突
            if overlap >= 3 and e_stmt.strip() != statement.strip():
                return e_id
        return None

    # --------------------------------------------------------------------------
    # 第 5 层：级联依赖检查引擎 (Cascade Stale Recalc)
    # --------------------------------------------------------------------------
    def _cascade_stale_recalc(self, conn, deleted_id: str, now_iso: str):
        """当底层事实被修改或删除时，查找所有依赖它的上层衍生结论，自动标记为待重算，杜绝僵尸结论."""
        rows = conn.execute(
            "SELECT id, statement, derived_from FROM memories WHERE derived_from LIKE ? AND status NOT IN ('redacted', 'soft_deleted')",
            (f"%{deleted_id}%",)
        ).fetchall()

        for der_id, der_stmt, der_from in rows:
            conn.execute("UPDATE memories SET status='stale_recalc', updated_at=? WHERE id=?",
                         (now_iso, der_id))
            self._log_audit(
                conn, der_id, "cascade_stale_recalc", "active", "stale_recalc",
                "cascade_engine", f"前置依赖证据 [{deleted_id}] 变更或删除，本条推导结论需重新提炼"
            )

    def _log_audit(self, conn, memory_id: str, action: str, old_val: str, new_val: str,
                   operator: str, reason: str, ts: Optional[str] = None):
        ts = ts or now_utc_iso()
        conn.execute("""
            INSERT INTO memory_audit_log(memory_id, action, old_value, new_value, operator, reason, ts)
            VALUES(?,?,?,?,?,?,?)
        """, (memory_id, action, old_val, new_val, operator, reason, ts))

    # --------------------------------------------------------------------------
    # 公共核心 API：录入、印证、演进、裁决、删除、查询
    # --------------------------------------------------------------------------
    def add_memory(self, statement: str, category: str = "preference",
                   source_type: str = SourceType.DIRECT_STATEMENT.value,
                   sensitivity: str = Sensitivity.L1.value,
                   scope: str = Scope.GENERAL.value,
                   source_client: str = "local",
                   source_agent: str = "manual",
                   source_session: str = "manual_entry",
                   source_snippet: str = "",
                   derived_from: str = "",
                   check_conflict: bool = True,
                   operator: str = "user") -> Dict[str, Any]:
        """第1/3/4/6层: 录入记忆事实 (带来源定级、差分置信度与冲突隔离检测)."""
        statement = statement.strip()
        if not statement:
            raise ValueError("statement cannot be empty")

        mid = f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(2)}"
        now_iso = now_utc_iso()

        # 第3层: 依来源给定初始置信度
        if source_type == SourceType.DIRECT_STATEMENT.value:
            conf = 1.0
        elif source_type == SourceType.TOOL_EVENT.value:
            conf = 0.85
        else:
            conf = 0.55

        conn = self.storage.get_connection()
        try:
            status = MemoryStatus.ACTIVE.value
            conflict_partner = ""

            # 第4层: 冲突检测
            if check_conflict:
                conflict_partner = self._detect_conflict(conn, category, scope, statement)
                if conflict_partner:
                    status = MemoryStatus.CONFLICTED.value
                    # 双向隔离：将已有条目也置为 conflicted，暂停提示词注入
                    conn.execute("UPDATE memories SET status='conflicted', conflict_with=?, updated_at=? WHERE id=?",
                                 (mid, now_iso, conflict_partner))
                    self._log_audit(
                        conn, conflict_partner, "conflict_quarantine", "active", f"conflicted with {mid}",
                        "conflict_detector", "疑似与新录入记忆冲突，双向隔离待裁决"
                    )

            conn.execute("""
                INSERT INTO memories(id, category, statement, confidence, status, superseded_by, supersedes_id,
                                     sensitivity, scope, source_client, source_agent, source_session, source_snippet,
                                     source_type, reinforced_count, last_reinforced_at, derived_from, conflict_with,
                                     grace_until, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                mid, category, statement, conf, status, "", "",
                sensitivity, scope, source_client, source_agent, source_session, source_snippet,
                source_type, 1, now_iso, derived_from, conflict_partner or "",
                "", now_iso, now_iso
            ))

            self._log_audit(conn, mid, "create", "", statement, operator,
                            f"录入事实({source_type}, 初始置信度:{conf})")
            conn.commit()

            return {
                "id": mid,
                "status": status,
                "confidence": conf,
                "conflict_with": conflict_partner,
                "created_at": now_iso
            }
        finally:
            conn.close()

    def reinforce(self, memory_id: str, snippet: str = "", operator: str = "agent") -> Dict[str, Any]:
        """第3层: 印证强化 (+0.1 置信度，若处于待复核则自动转正)."""
        conn = self.storage.get_connection()
        now_iso = now_utc_iso()
        try:
            row = conn.execute("SELECT confidence, reinforced_count, status FROM memories WHERE id=?", (memory_id,)).fetchone()
            if not row:
                raise KeyError(f"memory {memory_id} not found")
            old_conf, r_count, status = row
            new_conf = min(1.0, round(old_conf + 0.1, 2))
            new_status = status
            if status == MemoryStatus.PENDING_REVIEW.value and new_conf >= 0.60:
                new_status = MemoryStatus.ACTIVE.value

            conn.execute("""
                UPDATE memories SET confidence=?, reinforced_count=?, last_reinforced_at=?, status=?, updated_at=?
                WHERE id=?
            """, (new_conf, r_count + 1, now_iso, new_status, now_iso, memory_id))

            reason = f"事实再次印证 (置信度 {old_conf} -> {new_conf}, 累计 {r_count + 1} 次)"
            if snippet:
                reason += f" 证据: {snippet[:80]}"
            self._log_audit(conn, memory_id, "reinforce", str(old_conf), str(new_conf), operator, reason)
            conn.commit()
            return {"id": memory_id, "confidence": new_conf, "reinforced_count": r_count + 1, "status": new_status}
        finally:
            conn.close()

    def supersede(self, memory_id: str, new_statement: str, reason: str = "偏好演进",
                  operator: str = "user", snippet: str = "") -> Dict[str, Any]:
        """第2层: 非破坏性演进替换 (旧记录指往新条目，新记录指回旧条目，全链路保留)."""
        new_statement = new_statement.strip()
        if not new_statement:
            raise ValueError("new_statement cannot be empty")

        new_mid = f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(2)}"
        now_iso = now_utc_iso()
        conn = self.storage.get_connection()
        try:
            old = conn.execute(
                "SELECT category, sensitivity, scope, source_client, source_agent, source_session FROM memories WHERE id=?",
                (memory_id,)
            ).fetchone()
            if not old:
                raise KeyError(f"memory {memory_id} not found")

            # 1. 插入新记录，记录 supersedes_id 指回旧条目
            conn.execute("""
                INSERT INTO memories(id, category, statement, confidence, status, superseded_by, supersedes_id,
                                     sensitivity, scope, source_client, source_agent, source_session, source_snippet,
                                     source_type, reinforced_count, last_reinforced_at, derived_from, conflict_with,
                                     grace_until, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                new_mid, old[0], new_statement, 1.0, MemoryStatus.ACTIVE.value, "", memory_id,
                old[1], old[2], old[3], old[4], old[5], snippet or f"演进自 {memory_id}",
                SourceType.DIRECT_STATEMENT.value, 1, now_iso, "", "", "", now_iso, now_iso
            ))

            # 2. 标记旧记录为 superseded，记录 superseded_by 指向新条目
            conn.execute("UPDATE memories SET status='superseded', superseded_by=?, updated_at=? WHERE id=?",
                         (new_mid, now_iso, memory_id))

            self._log_audit(conn, memory_id, "supersede", "", f"取代为: {new_mid} ({new_statement})",
                            operator, reason, now_iso)
            conn.commit()
            return {"old_id": memory_id, "new_id": new_mid, "created_at": now_iso}
        finally:
            conn.close()

    def arbitrate_conflict(self, memory_id: str, decision: str, custom_statement: str = "",
                           scope_this: str = "work", scope_partner: str = "personal",
                           operator: str = "user") -> Dict[str, Any]:
        """第4层: 冲突裁决仲裁 (以新代旧 / 维持旧条 / 场景分流共存 / 综合重写)."""
        conn = self.storage.get_connection()
        now_iso = now_utc_iso()
        try:
            row = conn.execute("SELECT conflict_with, statement, scope FROM memories WHERE id=?", (memory_id,)).fetchone()
            if not row:
                raise KeyError(f"memory {memory_id} not found")
            partner_id = row[0]

            if not partner_id:
                conn.execute("UPDATE memories SET status='active', conflict_with='', updated_at=? WHERE id=?",
                             (now_iso, memory_id))
                conn.commit()
                return {"message": "冲突已单方解除"}

            if decision == "keep_new":
                conn.execute("UPDATE memories SET status='active', conflict_with='', supersedes_id=?, updated_at=? WHERE id=?",
                             (partner_id, now_iso, memory_id))
                conn.execute("UPDATE memories SET status='superseded', conflict_with='', superseded_by=?, updated_at=? WHERE id=?",
                             (memory_id, now_iso, partner_id))
                desc = f"采纳本条({memory_id})，归档旧条({partner_id})"
            elif decision == "keep_old":
                conn.execute("UPDATE memories SET status='active', conflict_with='', updated_at=? WHERE id=?",
                             (now_iso, partner_id))
                conn.execute("UPDATE memories SET status='superseded', conflict_with='', superseded_by=?, updated_at=? WHERE id=?",
                             (partner_id, now_iso, memory_id))
                desc = f"保留旧条({partner_id})，废弃本条({memory_id})"
            elif decision == "coexist":
                conn.execute("UPDATE memories SET status='active', conflict_with='', scope=?, updated_at=? WHERE id=?",
                             (scope_this, now_iso, memory_id))
                conn.execute("UPDATE memories SET status='active', conflict_with='', scope=?, updated_at=? WHERE id=?",
                             (scope_partner, now_iso, partner_id))
                desc = f"场景分流共存：{memory_id} ➔ {scope_this}, {partner_id} ➔ {scope_partner}"
            elif decision == "custom":
                if not custom_statement:
                    raise ValueError("custom_statement cannot be empty")
                conn.execute("UPDATE memories SET status='superseded', conflict_with='', updated_at=? WHERE id IN (?,?)",
                             (now_iso, memory_id, partner_id))
                new_res = self.add_memory(custom_statement, category="preference", operator=operator)
                desc = f"重构为新记忆: {new_res['id']}"
            else:
                raise ValueError(f"unknown decision: {decision}")

            self._log_audit(conn, memory_id, "arbitrate", decision, desc, operator, "冲突仲裁生效")
            conn.commit()
            return {"decision": decision, "description": desc}
        finally:
            conn.close()

    def soft_delete(self, memory_id: str, reason: str = "用户软删除", operator: str = "user") -> Dict[str, Any]:
        """第5层: 软删除 (保留30天回收期，自动触发下游证据链断裂级联重算)."""
        conn = self.storage.get_connection()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat(timespec="seconds")
        grace_until = (now + timedelta(days=30)).isoformat(timespec="seconds")
        try:
            conn.execute("UPDATE memories SET status='soft_deleted', grace_until=?, updated_at=? WHERE id=?",
                         (grace_until, now_iso, memory_id))
            self._log_audit(conn, memory_id, "soft_delete", "", f"grace_until:{grace_until}", operator, reason)
            # 触发级联检查
            self._cascade_stale_recalc(conn, memory_id, now_iso)
            conn.commit()
            return {"id": memory_id, "status": "soft_deleted", "grace_until": grace_until}
        finally:
            conn.close()

    def restore(self, memory_id: str, operator: str = "user") -> Dict[str, Any]:
        """第5层: 从回收期恢复活跃."""
        conn = self.storage.get_connection()
        now_iso = now_utc_iso()
        try:
            conn.execute("UPDATE memories SET status='active', grace_until='', updated_at=? WHERE id=?",
                         (now_iso, memory_id))
            self._log_audit(conn, memory_id, "restore", "soft_deleted", "active", operator, "从回收期恢复")
            conn.commit()
            return {"id": memory_id, "status": "active"}
        finally:
            conn.close()

    def forget(self, memory_id: str, reason: str = "永久遗忘", operator: str = "user") -> Dict[str, Any]:
        """第5层: 永久遗忘封存 (置为 redacted，下游结论进入待重算)."""
        conn = self.storage.get_connection()
        now_iso = now_utc_iso()
        try:
            conn.execute("UPDATE memories SET status='redacted', updated_at=? WHERE id=?", (now_iso, memory_id))
            self._log_audit(conn, memory_id, "redact", "", "REDACTED", operator, reason)
            self._cascade_stale_recalc(conn, memory_id, now_iso)
            conn.commit()
            return {"id": memory_id, "status": "redacted"}
        finally:
            conn.close()

    def get_memories(self, query: str = "", category: str = "", status: str = "",
                     source_type: str = "", sensitivity: str = "",
                     allowed_sensitivities: Optional[List[str]] = None,
                     scope: str = "", include_inactive: bool = False,
                     limit: int = 100) -> List[Memory]:
        """第1/2/6层: 全维度审查检索 (支持分级授权过滤)."""
        self.apply_confidence_decay()
        conn = self.storage.get_connection()
        try:
            sql = ("SELECT id, category, statement, confidence, status, source_type, sensitivity, scope, "
                   "source_client, source_agent, source_session, source_snippet, superseded_by, supersedes_id, "
                   "reinforced_count, last_reinforced_at, derived_from, conflict_with, grace_until, created_at, updated_at "
                   "FROM memories WHERE 1=1")
            params = []

            if status:
                statuses = [s.strip() for s in status.split(",") if s.strip()]
                sql += f" AND status IN ({','.join('?' for _ in statuses)})"
                params.extend(statuses)
            elif not include_inactive:
                sql += " AND status NOT IN ('redacted', 'soft_deleted', 'superseded')"

            if category:
                sql += " AND category=?"
                params.append(category)

            if source_type:
                sql += " AND source_type=?"
                params.append(source_type)

            # 第6层: 分级授权过滤
            if allowed_sensitivities:
                sql += f" AND sensitivity IN ({','.join('?' for _ in allowed_sensitivities)})"
                params.extend(allowed_sensitivities)
            elif sensitivity:
                sql += " AND sensitivity=?"
                params.append(sensitivity)

            if scope:
                sql += " AND scope=?"
                params.append(scope)

            if query:
                sql += " AND (statement LIKE ? OR source_snippet LIKE ? OR id LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

            # 优先级排序: 冲突隔离 > 衰减待复核 > 加固 > 活跃 > 待重算
            sql += """ ORDER BY 
                CASE status 
                    WHEN 'conflicted' THEN 1 
                    WHEN 'pending_review' THEN 2 
                    WHEN 'pinned' THEN 3 
                    WHEN 'active' THEN 4 
                    WHEN 'stale_recalc' THEN 5 
                    ELSE 6 
                END, updated_at DESC LIMIT ?"""
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            out = []
            for r in rows:
                out.append(Memory(
                    id=r[0], category=r[1], statement=r[2], confidence=r[3], status=r[4],
                    source_type=r[5], sensitivity=r[6], scope=r[7], source_client=r[8],
                    source_agent=r[9], source_session=r[10], source_snippet=r[11],
                    superseded_by=r[12], supersedes_id=r[13], reinforced_count=r[14],
                    last_reinforced_at=r[15], derived_from=r[16], conflict_with=r[17],
                    grace_until=r[18], created_at=r[19], updated_at=r[20]
                ))
            return out
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """获取六层治理状态全维度统计报表."""
        conn = self.storage.get_connection()
        try:
            stats = {
                "active": 0, "pinned": 0, "conflicted": 0, "pending_review": 0,
                "stale_recalc": 0, "superseded": 0, "soft_deleted": 0, "redacted": 0, "total": 0,
                "by_source_type": {"direct_statement": 0, "ai_inference": 0, "tool_event": 0},
                "by_sensitivity": {"L0": 0, "L1": 0, "L2": 0},
                "by_scope": {"general": 0, "work": 0, "personal": 0}
            }
            for s, cnt in conn.execute("SELECT status, count(*) FROM memories GROUP BY status").fetchall():
                stats[s] = cnt
                stats["total"] += cnt
            for st, cnt in conn.execute("SELECT source_type, count(*) FROM memories WHERE status NOT IN ('redacted','soft_deleted') GROUP BY source_type").fetchall():
                if st in stats["by_source_type"]:
                    stats["by_source_type"][st] = cnt
            for sens, cnt in conn.execute("SELECT sensitivity, count(*) FROM memories WHERE status NOT IN ('redacted','soft_deleted') GROUP BY sensitivity").fetchall():
                if sens in stats["by_sensitivity"]:
                    stats["by_sensitivity"][sens] = cnt
            for sc, cnt in conn.execute("SELECT scope, count(*) FROM memories WHERE status NOT IN ('redacted','soft_deleted') GROUP BY scope").fetchall():
                if sc in stats["by_scope"]:
                    stats["by_scope"][sc] = cnt
            return stats
        finally:
            conn.close()

    def get_audit_logs(self, limit: int = 60) -> List[AuditLog]:
        conn = self.storage.get_connection()
        try:
            rows = conn.execute(
                "SELECT id, memory_id, action, old_value, new_value, operator, reason, ts FROM memory_audit_log ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [AuditLog(id=r[0], memory_id=r[1], action=r[2], old_value=r[3],
                             new_value=r[4], operator=r[5], reason=r[6], ts=r[7]) for r in rows]
        finally:
            conn.close()
