# -*- coding: utf-8 -*-
"""OpenMemory - Core Data Models and Enumerations."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


class SourceType(str, Enum):
    """Layer 1: Provenance classification."""
    DIRECT_STATEMENT = "direct_statement"  # 用户直接原话陈述 (置信度 1.0)
    AI_INFERENCE = "ai_inference"          # AI 自主提炼推断 (初始置信度 0.55，动态衰减)
    TOOL_EVENT = "tool_event"              # 工具执行客观事件 (初始置信度 0.85)


class MemoryStatus(str, Enum):
    """Layer 2/3/4/5: Lifecycle status."""
    ACTIVE = "active"                      # 活跃有效
    PINNED = "pinned"                      # 黄金加固 (铁律，不参与衰减)
    CONFLICTED = "conflicted"              # 冲突隔离 (双向隔离，暂停提示词注入)
    PENDING_REVIEW = "pending_review"      # 衰减待复核 (置信度低于阈值，待确认)
    STALE_RECALC = "stale_recalc"          # 依赖待重算 (前置证据被删，结论待重构)
    SUPERSEDED = "superseded"              # 历史取代 (非破坏性演进保留)
    SOFT_DELETED = "soft_deleted"          # 软删除回收期 (30天可恢复)
    REDACTED = "redacted"                  # 永久遗忘封存


class Sensitivity(str, Enum):
    """Layer 6: Tiered authorization levels."""
    L0 = "L0"  # 公开偏好 (所有 AI 工具通用，如语言偏好、简洁风格)
    L1 = "L1"  # 工程上下文 (仅限私有/受信开发环境，如服务拓扑、项目规则)
    L2 = "L2"  # 个人机密 (严格隔离，严禁无授权随普通提示词扩散)


class Scope(str, Enum):
    """Layer 4: Contextual scope."""
    GENERAL = "general"    # 全局通用
    WORK = "work"          # 工作/项目
    PERSONAL = "personal"  # 个人生活/娱乐


@dataclass
class Memory:
    id: str
    statement: str
    category: str = "preference"
    confidence: float = 1.0
    status: str = MemoryStatus.ACTIVE.value
    source_type: str = SourceType.DIRECT_STATEMENT.value
    sensitivity: str = Sensitivity.L1.value
    scope: str = Scope.GENERAL.value
    source_client: str = "local"
    source_agent: str = "manual"
    source_session: str = "manual_entry"
    source_snippet: str = ""
    superseded_by: str = ""
    supersedes_id: str = ""
    reinforced_count: int = 1
    last_reinforced_at: str = ""
    derived_from: str = ""
    conflict_with: str = ""
    grace_until: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Memory:
        # 兼容缺省字段
        fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in fields}
        return cls(**filtered)


@dataclass
class AuditLog:
    id: Optional[int]
    memory_id: str
    action: str
    old_value: str
    new_value: str
    operator: str
    reason: str
    ts: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
