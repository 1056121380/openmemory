# -*- coding: utf-8 -*-
"""OpenMemory - Server Application & Web Review Console."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse

from core import GovernanceEngine, Storage, MemoryBundle, get_default_data_dir

app = FastAPI(title="OpenMemory Hub & Governance Console", version="2.0.0")

DATA_DIR = Path(os.environ.get("OPENMEMORY_DATA_DIR", "")).expanduser().resolve() if os.environ.get("OPENMEMORY_DATA_DIR") else get_default_data_dir()
QUERY_TOKEN = os.environ.get("HUB_QUERY_TOKEN", "").strip()
INGEST_TOKENS = [t.strip() for t in os.environ.get("HUB_INGEST_TOKENS", "").split(",") if t.strip()]

storage = Storage(DATA_DIR / "memory.db")
engine = GovernanceEngine(storage)


def _auth_query(request: Request, authorization: str = "") -> None:
    if not QUERY_TOKEN:
        return  # 未设 token 时默认为本地单机/开发模式，直接放行
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif request.headers.get("authorization", "").startswith("Bearer "):
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token").strip()
    elif request.cookies.get("hub_token"):
        token = request.cookies.get("hub_token").strip()

    if token != QUERY_TOKEN:
        raise HTTPException(401, "invalid query token")


def _auth_ingest(request: Request, authorization: str = "") -> None:
    if not INGEST_TOKENS:
        return
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif request.headers.get("authorization", "").startswith("Bearer "):
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if token not in INGEST_TOKENS:
        raise HTTPException(401, "invalid ingest token")


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "openmemory", "version": "2.0.0"}


# ------------------------------------------------------------------------------
# 治理层核心 REST API (6-Layer Governance API)
# ------------------------------------------------------------------------------

@app.get("/v1/governance/memories")
def list_memories(request: Request, status: str = "", category: str = "",
                  sensitivity: str = "", allowed_sensitivities: str = "",
                  source_type: str = "", scope: str = "", q: str = "",
                  include_inactive: bool = False, limit: int = 100,
                  authorization: str = Header(default="")):
    _auth_query(request, authorization)
    allowed_list = [s.strip() for s in allowed_sensitivities.split(",") if s.strip()] if allowed_sensitivities else None
    mems = engine.get_memories(
        query=q, category=category, status=status, source_type=source_type,
        sensitivity=sensitivity, allowed_sensitivities=allowed_list,
        scope=scope, include_inactive=include_inactive, limit=limit
    )
    return {"memories": [m.to_dict() for m in mems], "total": len(mems)}


@app.post("/v1/governance/memories")
async def create_memory(request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    body = await request.json()
    res = engine.add_memory(
        statement=body.get("statement", ""),
        category=body.get("category", "preference"),
        source_type=body.get("source_type", "direct_statement"),
        sensitivity=body.get("sensitivity", "L1"),
        scope=body.get("scope", "general"),
        source_client=body.get("source_client", "client"),
        source_agent=body.get("source_agent", "manual"),
        source_session=body.get("source_session", "manual_entry"),
        source_snippet=body.get("source_snippet", ""),
        derived_from=body.get("derived_from", ""),
        check_conflict=body.get("check_conflict", True),
        operator=body.get("operator", "user")
    )
    return {"ok": True, **res}


@app.post("/v1/governance/memories/{mem_id}/reinforce")
async def reinforce_memory(mem_id: str, request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    body = await request.json() if request.headers.get("content-length") else {}
    res = engine.reinforce(mem_id, snippet=body.get("snippet", ""), operator=body.get("operator", "user"))
    return {"ok": True, **res}


@app.post("/v1/governance/memories/{mem_id}/supersede")
async def supersede_memory(mem_id: str, request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    body = await request.json()
    res = engine.supersede(
        mem_id,
        new_statement=body.get("new_statement", ""),
        reason=body.get("reason", "用户纠偏演进"),
        operator=body.get("operator", "user"),
        snippet=body.get("source_snippet", "")
    )
    return {"ok": True, **res}


@app.post("/v1/governance/conflicts/{mem_id}/arbitrate")
async def arbitrate_conflict(mem_id: str, request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    body = await request.json()
    res = engine.arbitrate_conflict(
        mem_id,
        decision=body.get("decision", "keep_new"),
        custom_statement=body.get("custom_statement", ""),
        scope_this=body.get("scope_this", "work"),
        scope_partner=body.get("scope_partner", "personal"),
        operator=body.get("operator", "user")
    )
    return {"ok": True, **res}


@app.post("/v1/governance/memories/{mem_id}/soft_delete")
async def soft_delete(mem_id: str, request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    body = await request.json() if request.headers.get("content-length") else {}
    res = engine.soft_delete(mem_id, reason=body.get("reason", "用户软删除"), operator=body.get("operator", "user"))
    return {"ok": True, **res}


@app.post("/v1/governance/memories/{mem_id}/restore")
async def restore(mem_id: str, request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    res = engine.restore(mem_id, operator="user")
    return {"ok": True, **res}


@app.post("/v1/governance/memories/{mem_id}/forget")
async def forget(mem_id: str, request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    body = await request.json() if request.headers.get("content-length") else {}
    res = engine.forget(mem_id, reason=body.get("reason", "用户一键遗忘"), operator=body.get("operator", "user"))
    return {"ok": True, **res}


@app.get("/v1/governance/stats")
def governance_stats(request: Request, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    return engine.get_stats()


@app.get("/v1/governance/audit")
def governance_audit(request: Request, limit: int = 60, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    logs = engine.get_audit_logs(limit=limit)
    return {"audit_logs": [l.to_dict() for l in logs]}


# ------------------------------------------------------------------------------
# 导入导出 API (Bundle Export/Import)
# ------------------------------------------------------------------------------

@app.get("/v1/governance/export")
def export_bundle(request: Request, format: str = "json", authorization: str = Header(default="")):
    _auth_query(request, authorization)
    temp_dir = DATA_DIR / "export"
    temp_dir.mkdir(parents=True, exist_ok=True)
    if format == "json":
        out_f = temp_dir / "openmemory_bundle.json"
        cnt = MemoryBundle.export_json(engine, out_f)
        return JSONResponse(json.loads(out_f.read_text(encoding="utf-8")))
    else:
        out_d = temp_dir / "vault"
        cnt = MemoryBundle.export_markdown_vault(engine, out_d)
        return {"ok": True, "format": "markdown", "vault_path": str(out_d), "count": cnt}


# ------------------------------------------------------------------------------
# 全文检索与会话接入 (FTS Search & Session Ingest)
# ------------------------------------------------------------------------------

@app.get("/v1/search")
def fts_search(request: Request, q: str = "", limit: int = 15, authorization: str = Header(default="")):
    _auth_query(request, authorization)
    if not q.strip():
        return {"query": q, "results": []}
    conn = storage.get_connection()
    try:
        sql = ("SELECT client, agent, session_id, snippet(fts, 4, '«', '»', '...', 32) "
               "FROM fts WHERE body MATCH ? ORDER BY rank LIMIT ?")
        rows = conn.execute(sql, (q, limit)).fetchall()
        return {
            "query": q,
            "results": [{"client": r[0], "agent": r[1], "session_id": r[2], "snippet": r[3]} for r in rows]
        }
    except Exception:
        # FTS query syntax error fallback
        return {"query": q, "results": []}
    finally:
        conn.close()


@app.post("/v1/events")
async def ingest_event(request: Request, authorization: str = Header(default="")):
    _auth_ingest(request, authorization)
    body = await request.json()
    client = str(body.get("client", "unknown")).strip()
    agent = str(body.get("agent", "unknown")).strip()
    session_id = str(body.get("session_id", "unknown")).strip()
    payload = str(body.get("payload_text", "")).strip()

    raw_dir = DATA_DIR / "raw" / client / agent
    raw_dir.mkdir(parents=True, exist_ok=True)
    f = raw_dir / f"{session_id}.jsonl"

    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(body, ensure_ascii=False) + "\n")

    # 同步写入 FTS
    if payload:
        conn = storage.get_connection()
        try:
            rel = f"{client}/{agent}/{session_id}.jsonl"
            conn.execute("INSERT INTO fts(path,client,agent,session_id,body) VALUES(?,?,?,?,?)",
                         (rel, client, agent, session_id, payload[:300_000]))
            conn.commit()
        finally:
            conn.close()

    return {"ok": True, "status": "ingested"}


# ------------------------------------------------------------------------------
# Web 控制台单页应用 (Console Single-Page HTML)
# ------------------------------------------------------------------------------

WEB_UI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenMemory - 跨 Agent AI 记忆中枢与审查控制台</title>
  <style>
    :root {
      --bg: #0b1120; --card-bg: #1e293b; --border: #334155; --text: #f8fafc;
      --text-muted: #94a3b8; --primary: #38bdf8; --primary-hover: #0ea5e9;
      --accent: #10b981; --danger: #ef4444; --warning: #f59e0b; --purple: #a855f7;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif; }
    body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
    header { background: #0f172a; border-bottom: 1px solid var(--border); padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
    .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.15rem; color: #fff; }
    .badge { font-size: 0.72rem; padding: 3px 8px; border-radius: 9999px; background: rgba(56, 189, 248, 0.15); color: var(--primary); border: 1px solid rgba(56, 189, 248, 0.3); }
    .nav-tabs { display: flex; gap: 8px; }
    .tab-btn { background: transparent; border: none; color: var(--text-muted); padding: 8px 16px; border-radius: 6px; font-size: 0.9rem; cursor: pointer; transition: all 0.2s; }
    .tab-btn:hover { color: #fff; background: rgba(255,255,255,0.05); }
    .tab-btn.active { color: #fff; background: var(--card-bg); font-weight: 600; border: 1px solid var(--border); }
    
    main { flex: 1; padding: 24px; max-width: 1380px; margin: 0 auto; width: 100%; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }
    .stat-box { background: #131d31; border: 1px solid var(--border); border-radius: 10px; padding: 14px; cursor: pointer; transition: transform 0.15s; }
    .stat-box:hover { transform: translateY(-2px); border-color: var(--primary); }
    .stat-val { font-size: 1.7rem; font-weight: 800; color: var(--primary); margin-top: 4px; }
    .stat-lbl { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; }
    
    .toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
    input, select, textarea { background: #0f172a; border: 1px solid var(--border); color: #fff; padding: 7px 12px; border-radius: 6px; font-size: 0.88rem; outline: none; }
    input:focus, select:focus, textarea:focus { border-color: var(--primary); }
    .btn { background: var(--primary); color: #0f172a; border: none; padding: 7px 14px; border-radius: 6px; font-size: 0.88rem; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary { background: #334155; color: #fff; }
    .btn-secondary:hover { background: #475569; }
    .btn-danger { background: #dc2626; color: #fff; }
    .btn-warning { background: #d97706; color: #fff; }
    .btn-sm { padding: 4px 10px; font-size: 0.78rem; }
    
    .tag { display: inline-block; background: #0f172a; border: 1px solid var(--border); border-radius: 4px; padding: 2px 7px; font-size: 0.74rem; margin-right: 4px; color: #cbd5e1; }
    .gov-card { background: #131d31; border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; margin-bottom: 12px; position: relative; }
    .gov-card.pinned { border-left: 5px solid #eab308; }
    .gov-card.conflicted { border-left: 5px solid var(--danger); background: #20131b; }
    .gov-card.pending_review { border-left: 5px solid var(--warning); background: #1f1b13; }
    .gov-card.stale_recalc { border-left: 5px solid #06b6d4; background: #0e1e28; }
    .gov-card.superseded { opacity: 0.6; border-left: 4px solid #64748b; }
    .gov-card.superseded .gov-stmt { text-decoration: line-through; }
    .gov-card.soft_deleted { opacity: 0.5; border-left: 4px dashed var(--danger); }
    .gov-card.soft_deleted .gov-stmt { text-decoration: line-through; }
    .gov-stmt { font-size: 0.98rem; color: #f1f5f9; line-height: 1.5; font-weight: 500; margin-bottom: 8px; }
    .gov-meta { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 0.78rem; color: var(--text-muted); }
    .trace-drawer { background: #0f172a; border: 1px dashed #334155; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 0.8rem; }
    .trace-snippet { border-left: 3px solid var(--primary); padding-left: 10px; color: #cbd5e1; font-family: monospace; white-space: pre-wrap; margin-top: 6px; }
    
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: none; align-items: center; justify-content: center; z-index: 1000; padding: 20px; }
    .modal { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; width: 100%; max-width: 700px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
    .modal-header { padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-weight: 700; }
    .modal-body { padding: 18px; overflow-y: auto; flex: 1; }
    .modal-footer { padding: 12px 18px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 10px; background: #131d31; }
    .hidden { display: none !important; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>🧠 OpenMemory</span>
      <span class="badge">开源版 v2.0</span>
    </div>
    <div class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('gov')">🛡️ 记忆治理控制台</button>
      <button class="tab-btn" onclick="switchTab('search')">🔍 全文检索</button>
      <button class="tab-btn" onclick="switchTab('audit')">📜 变更审计流水</button>
    </div>
    <div style="display:flex;gap:8px;">
      <button class="btn btn-secondary btn-sm" onclick="exportData('json')">📦 导出 JSON</button>
      <button class="btn btn-secondary btn-sm" onclick="exportData('vault')">📁 导出 Markdown Vault</button>
    </div>
  </header>

  <main>
    <section id="tab-gov">
      <div class="stats-grid">
        <div class="stat-box" onclick="filterStatus('pinned')"><div class="stat-lbl">📌 黄金加固 (Pinned)</div><div class="stat-val" id="cntPinned" style="color:#eab308;">0</div></div>
        <div class="stat-box" onclick="filterStatus('active')"><div class="stat-lbl">⚡ 活跃有效 (Active)</div><div class="stat-val" id="cntActive" style="color:var(--accent);">0</div></div>
        <div class="stat-box" onclick="filterStatus('conflicted')"><div class="stat-lbl">⚖️ 冲突隔离 (Conflicted)</div><div class="stat-val" id="cntConflicted" style="color:var(--danger);">0</div></div>
        <div class="stat-box" onclick="filterStatus('pending_review')"><div class="stat-lbl">⚠️ 衰减待复核 (Review)</div><div class="stat-val" id="cntReview" style="color:var(--warning);">0</div></div>
        <div class="stat-box" onclick="filterStatus('stale_recalc')"><div class="stat-lbl">🔄 依赖待重算 (Stale)</div><div class="stat-val" id="cntStale" style="color:#06b6d4;">0</div></div>
        <div class="stat-box" onclick="filterStatus('superseded')"><div class="stat-lbl">⏳ 已取代 (Superseded)</div><div class="stat-val" id="cntSuper" style="color:#94a3b8;">0</div></div>
      </div>

      <div class="toolbar" style="background:#131d31; border:1px solid var(--border); border-radius:10px; padding:12px; margin-bottom:14px;">
        <input type="text" id="filterQ" placeholder="搜索事实关键词、ID 或原话..." style="flex:1;" oninput="loadMemories()">
        <select id="filterCat" onchange="loadMemories()">
          <option value="">全部类别</option>
          <option value="preference">💡 个人偏好</option>
          <option value="rule">⚖️ 铁律禁忌</option>
          <option value="architecture">🏗️ 架构设施</option>
          <option value="project">🚀 工程项目</option>
          <option value="anti_pattern">🛡️ 避坑经验</option>
        </select>
        <select id="filterSourceType" onchange="loadMemories()">
          <option value="">全部来源类型</option>
          <option value="direct_statement">🗣️ 用户原话 (置信 1.0)</option>
          <option value="ai_inference">🤖 AI推断 (动态衰减)</option>
          <option value="tool_event">🛠️ 工具事件 (置信 0.85)</option>
        </select>
        <select id="filterSens" onchange="loadMemories()">
          <option value="">全部授权级别</option>
          <option value="L0">L0 - 公开 (全 AI 可见)</option>
          <option value="L1">L1 - 工程内部 (限私网)</option>
          <option value="L2">L2 - 机密</option>
        </select>
        <select id="filterScope" onchange="loadMemories()">
          <option value="">全部场景</option>
          <option value="general">🌐 全局</option>
          <option value="work">💼 工作</option>
          <option value="personal">🏠 个人</option>
        </select>
        <select id="filterStatus" onchange="loadMemories()">
          <option value="">全部状态</option>
          <option value="active">⚡ 活跃</option>
          <option value="pinned">📌 加固</option>
          <option value="conflicted">⚖️ 冲突隔离</option>
          <option value="pending_review">⚠️ 衰减待复核</option>
          <option value="stale_recalc">🔄 依赖待重算</option>
          <option value="superseded">⏳ 已取代</option>
          <option value="soft_deleted">🗑️ 软删除</option>
        </select>
        <button class="btn btn-sm" onclick="showCreateModal()">+ 新建记忆</button>
      </div>

      <div id="cardsList">加载中...</div>
    </section>

    <section id="tab-search" class="hidden">
      <div style="background:#131d31; border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:16px;">
        <div class="toolbar">
          <input type="text" id="ftsQuery" placeholder="跨工具全文检索 (FTS5 Trigram)..." style="flex:1;" onkeydown="if(event.key==='Enter')doFtsSearch()">
          <button class="btn" onclick="doFtsSearch()">🔍 检索</button>
        </div>
        <div id="ftsResults"></div>
      </div>
    </section>

    <section id="tab-audit" class="hidden">
      <div id="auditList" style="background:#131d31; border:1px solid var(--border); border-radius:10px; padding:16px;">加载中...</div>
    </section>
  </main>

  <!-- 冲突裁决弹窗 -->
  <div class="modal-backdrop" id="arbModal">
    <div class="modal">
      <div class="modal-header"><span>⚖️ 冲突裁决与仲裁 (Conflict Arbitration)</span><button class="btn btn-secondary btn-sm" onclick="closeModal('arbModal')">✕</button></div>
      <div class="modal-body">
        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:12px;">两项记忆在相同分类/场景内陈述相左，已进入双向隔离。请选择处理方式：</p>
        <input type="hidden" id="arbId">
        <div style="display:flex;flex-direction:column;gap:8px;font-size:0.86rem;margin-bottom:14px;">
          <label style="cursor:pointer;"><input type="radio" name="arbDec" value="keep_new" checked> <strong>以新代旧</strong>：采纳本条，旧条目归档为 superseded</label>
          <label style="cursor:pointer;"><input type="radio" name="arbDec" value="keep_old"> <strong>维持旧条</strong>：保留旧条目，废弃本条</label>
          <label style="cursor:pointer;"><input type="radio" name="arbDec" value="coexist"> <strong>场景分流共存</strong>：两者均有效（本条归为工作，关联条归为个人）</label>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal('arbModal')">取消</button>
        <button class="btn btn-warning" onclick="submitArbitration()">确认裁决</button>
      </div>
    </div>
  </div>

  <!-- 新建记忆弹窗 -->
  <div class="modal-backdrop" id="createModal">
    <div class="modal">
      <div class="modal-header"><span>+ 新建记忆事实</span><button class="btn btn-secondary btn-sm" onclick="closeModal('createModal')">✕</button></div>
      <div class="modal-body">
        <div style="margin-bottom:12px;"><label style="display:block;font-size:0.83rem;margin-bottom:4px;color:var(--text-muted);">陈述 (Statement):</label><textarea id="newStmt" rows="3" style="width:100%;"></textarea></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
          <div><label style="display:block;font-size:0.83rem;margin-bottom:4px;color:var(--text-muted);">类别:</label><select id="newCat" style="width:100%;"><option value="preference">💡 个人偏好</option><option value="rule">⚖️ 铁律禁忌</option><option value="architecture">🏗️ 架构设施</option><option value="project">🚀 工程项目</option><option value="anti_pattern">🛡️ 避坑经验</option></select></div>
          <div><label style="display:block;font-size:0.83rem;margin-bottom:4px;color:var(--text-muted);">来源类型:</label><select id="newSType" style="width:100%;"><option value="direct_statement">🗣️ 用户直接原话 (置信 1.0)</option><option value="ai_inference">🤖 AI 自主推断 (置信 0.55)</option><option value="tool_event">🛠️ 工具事件 (置信 0.85)</option></select></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
          <div><label style="display:block;font-size:0.83rem;margin-bottom:4px;color:var(--text-muted);">授权级别:</label><select id="newSens" style="width:100%;"><option value="L0">L0 - 公开</option><option value="L1" selected>L1 - 工程内部</option><option value="L2">L2 - 机密</option></select></div>
          <div><label style="display:block;font-size:0.83rem;margin-bottom:4px;color:var(--text-muted);">场景 Scope:</label><select id="newScope" style="width:100%;"><option value="general">🌐 全局</option><option value="work">💼 工作</option><option value="personal">🏠 个人</option></select></div>
        </div>
        <div><label style="display:block;font-size:0.83rem;margin-bottom:4px;color:var(--text-muted);">原话依据 (Snippet):</label><textarea id="newSnippet" rows="2" style="width:100%;"></textarea></div>
      </div>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal('createModal')">取消</button><button class="btn" onclick="saveNewMemory()">确认入库</button></div>
    </div>
  </div>

  <script>
    let allMems = [];

    async function api(path, opts = {}) {
      if (opts.body && typeof opts.body === 'object') {
        opts.body = JSON.stringify(opts.body);
        opts.headers = opts.headers || {};
        opts.headers['Content-Type'] = 'application/json';
      }
      const res = await fetch(path, opts);
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }

    function switchTab(name) {
      document.querySelectorAll('.tab-btn').forEach((b, i) => b.classList.toggle('active', (name==='gov'&&i===0)||(name==='search'&&i===1)||(name==='audit'&&i===2)));
      document.getElementById('tab-gov').classList.toggle('hidden', name !== 'gov');
      document.getElementById('tab-search').classList.toggle('hidden', name !== 'search');
      document.getElementById('tab-audit').classList.toggle('hidden', name !== 'audit');
      if (name === 'gov') loadMemories();
      if (name === 'audit') loadAudit();
    }

    function filterStatus(st) {
      document.getElementById('filterStatus').value = st;
      loadMemories();
    }

    async function loadMemories() {
      const q = document.getElementById('filterQ').value.trim();
      const cat = document.getElementById('filterCat').value;
      const stype = document.getElementById('filterSourceType').value;
      const sens = document.getElementById('filterSens').value;
      const scope = document.getElementById('filterScope').value;
      const status = document.getElementById('filterStatus').value;

      const p = new URLSearchParams();
      if (q) p.set('q', q);
      if (cat) p.set('category', cat);
      if (stype) p.set('source_type', stype);
      if (sens) p.set('sensitivity', sens);
      if (scope) p.set('scope', scope);
      if (status) p.set('status', status);
      else p.set('include_inactive', 'true');

      try {
        const data = await api('/v1/governance/memories?' + p.toString());
        allMems = data.memories || [];
        renderCards();
        loadStats();
      } catch (e) {
        document.getElementById('cardsList').innerHTML = `<div style="color:var(--danger)">加载失败: ${e.message}</div>`;
      }
    }

    async function loadStats() {
      try {
        const s = await api('/v1/governance/stats');
        document.getElementById('cntPinned').innerText = s.pinned || 0;
        document.getElementById('cntActive').innerText = s.active || 0;
        document.getElementById('cntConflicted').innerText = s.conflicted || 0;
        document.getElementById('cntReview').innerText = s.pending_review || 0;
        document.getElementById('cntStale').innerText = s.stale_recalc || 0;
        document.getElementById('cntSuper').innerText = s.superseded || 0;
      } catch (e) {}
    }

    function renderCards() {
      const el = document.getElementById('cardsList');
      if (!allMems.length) {
        el.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">暂无符合条件的记忆事实</div>';
        return;
      }
      el.innerHTML = allMems.map(m => {
        const isConf = m.status === 'conflicted';
        const isRev = m.status === 'pending_review';
        const isStale = m.status === 'stale_recalc';
        const isSuper = m.status === 'superseded';
        const isSoft = m.status === 'soft_deleted';
        return `
          <div class="gov-card ${m.status}" id="c_${m.id}">
            ${isConf ? `<div style="background:#ef444422;border:1px solid #ef444455;padding:6px 12px;border-radius:6px;margin-bottom:8px;font-size:0.8rem;display:flex;justify-content:space-between;align-items:center;"><span>⚠️ <strong>冲突隔离保护</strong>：本条与关联条目陈述相悖，已暂停注入提示词。</span><button class="btn btn-warning btn-sm" onclick="openArbModal('${m.id}')">⚖️ 立即裁决</button></div>` : ''}
            ${isRev ? `<div style="background:#f59e0b22;border:1px solid #f59e0b55;padding:6px 12px;border-radius:6px;margin-bottom:8px;font-size:0.8rem;display:flex;justify-content:space-between;align-items:center;"><span>⏳ <strong>推断自然衰减</strong>：长期未印证，置信度降至 ${(m.confidence*100).toFixed(0)}%，请确认。</span><button class="btn btn-sm" onclick="reinforce('${m.id}')">✅ 确认有效 (+0.1)</button></div>` : ''}
            ${isStale ? `<div style="background:#06b6d422;border:1px solid #06b6d455;padding:6px 12px;border-radius:6px;margin-bottom:8px;font-size:0.8rem;">🔄 <strong>证据链断裂</strong>：本结论依赖的前置证据已删除/变更，标记为待重新提炼。</div>` : ''}
            
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
              <div>
                <span class="tag">${m.category}</span>
                <span class="tag" style="color:#38bdf8;">${m.source_type}</span>
                <span class="tag">${m.sensitivity}</span>
                <span class="tag">${m.scope}</span>
                <span class="tag" style="color:#a855f7;">置信度: ${(m.confidence*100).toFixed(0)}%</span>
                <span class="tag">印证: ${m.reinforced_count}次</span>
              </div>
              <div style="display:flex;gap:6px;">
                ${!isSuper ? `<button class="btn btn-secondary btn-sm" onclick="reinforce('${m.id}')">➕ 印证</button>` : ''}
                ${!isSuper ? `<button class="btn btn-warning btn-sm" onclick="supersedePrompt('${m.id}')">🔄 演进</button>` : ''}
                ${!isSoft ? `<button class="btn btn-danger btn-sm" onclick="softDel('${m.id}')">🗑️ 软删</button>` : ''}
                ${isSoft ? `<button class="btn btn-secondary btn-sm" onclick="restore('${m.id}')">♻️ 恢复</button>` : ''}
              </div>
            </div>
            <div class="gov-stmt">${m.statement}</div>
            ${m.superseded_by ? `<div style="font-size:0.8rem;color:#f59e0b;margin-bottom:4px;">↳ 取代为: ${m.superseded_by}</div>` : ''}
            ${m.supersedes_id ? `<div style="font-size:0.8rem;color:#38bdf8;margin-bottom:4px;">↳ 演进自: ${m.supersedes_id}</div>` : ''}
            <div class="gov-meta">
              <span>创建: ${m.created_at}</span>
              <span style="cursor:pointer;color:var(--primary);" onclick="document.getElementById('tr_${m.id}').classList.toggle('hidden')">🔍 查看溯源</span>
            </div>
            <div class="trace-drawer hidden" id="tr_${m.id}">
              <div><strong>来源环境:</strong> ${m.source_client} / ${m.source_agent} (会话: ${m.source_session})</div>
              ${m.derived_from ? `<div><strong>依赖底层事实:</strong> ${m.derived_from}</div>` : ''}
              <div style="margin-top:6px;"><strong>原始事实证据:</strong></div>
              <div class="trace-snippet">${m.source_snippet || '（无直接引用）'}</div>
            </div>
          </div>
        `;
      }).join('');
    }

    async function reinforce(id) {
      await api(`/v1/governance/memories/${id}/reinforce`, { method: 'POST', body: {} });
      loadMemories();
    }

    async function softDel(id) {
      if (!confirm('移入30天回收期？依赖此项的结论将标记为待重算。')) return;
      await api(`/v1/governance/memories/${id}/soft_delete`, { method: 'POST', body: {} });
      loadMemories();
    }

    async function restore(id) {
      await api(`/v1/governance/memories/${id}/restore`, { method: 'POST', body: {} });
      loadMemories();
    }

    async function supersedePrompt(id) {
      const stmt = prompt('请输入取代本条的新事实描述:');
      if (!stmt) return;
      await api(`/v1/governance/memories/${id}/supersede`, { method: 'POST', body: { new_statement: stmt } });
      loadMemories();
    }

    function openArbModal(id) {
      document.getElementById('arbId').value = id;
      document.getElementById('arbModal').style.display = 'flex';
    }

    async function submitArbitration() {
      const id = document.getElementById('arbId').value;
      const dec = document.querySelector('input[name="arbDec"]:checked').value;
      await api(`/v1/governance/conflicts/${id}/arbitrate`, { method: 'POST', body: { decision: dec } });
      closeModal('arbModal');
      loadMemories();
    }

    function showCreateModal() { document.getElementById('createModal').style.display = 'flex'; }
    function closeModal(id) { document.getElementById(id).style.display = 'none'; }

    async function saveNewMemory() {
      const stmt = document.getElementById('newStmt').value.trim();
      if (!stmt) return alert('陈述不能为空');
      await api('/v1/governance/memories', {
        method: 'POST',
        body: {
          statement: stmt,
          category: document.getElementById('newCat').value,
          source_type: document.getElementById('newSType').value,
          sensitivity: document.getElementById('newSens').value,
          scope: document.getElementById('newScope').value,
          source_snippet: document.getElementById('newSnippet').value.trim()
        }
      });
      closeModal('createModal');
      loadMemories();
    }

    async function doFtsSearch() {
      const q = document.getElementById('ftsQuery').value.trim();
      const el = document.getElementById('ftsResults');
      if (!q) return;
      el.innerHTML = '检索中...';
      const res = await api('/v1/search?q=' + encodeURIComponent(q));
      if (!res.results.length) { el.innerHTML = '无匹配会话记录。'; return; }
      el.innerHTML = res.results.map(r => `
        <div style="background:#0f172a;border:1px solid var(--border);border-radius:6px;padding:10px;margin-top:8px;">
          <div><span class="tag">${r.client}</span><span class="tag">${r.agent}</span><strong>${r.session_id}</strong></div>
          <div style="margin-top:4px;font-family:monospace;font-size:0.83rem;color:#cbd5e1;">${r.snippet}</div>
        </div>
      `).join('');
    }

    async function loadAudit() {
      const el = document.getElementById('auditList');
      el.innerHTML = '正在载入审计流水...';
      const data = await api('/v1/governance/audit?limit=60');
      el.innerHTML = (data.audit_logs || []).map(l => `
        <div style="border-bottom:1px solid #334155;padding:8px 0;font-size:0.82rem;">
          <div style="display:flex;justify-content:space-between;color:var(--text-muted);">
            <span><strong>${l.action}</strong> (${l.memory_id}) 操作者: ${l.operator}</span>
            <span>${l.ts}</span>
          </div>
          <div style="color:#fff;margin-top:2px;">理由: ${l.reason}</div>
          ${l.new_value ? `<div style="color:#94a3b8;font-family:monospace;">${l.new_value}</div>` : ''}
        </div>
      `).join('') || '暂无审计流水。';
    }

    function exportData(fmt) {
      window.open('/v1/governance/export?format=' + fmt, '_blank');
    }

    window.addEventListener('DOMContentLoaded', () => {
      loadMemories();
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return HTMLResponse(WEB_UI_HTML)


def start_server(host: str = "0.0.0.0", port: Optional[int] = None):
    import uvicorn
    p = port or int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host=host, port=p)


if __name__ == "__main__":
    start_server()
