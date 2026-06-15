#!/usr/bin/env python3
"""Local, auditable user-profile store for Codex skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


DEFAULT_BASE_DIR = Path.home() / ".compass-skills" / "user-profiles" / "v1"
BASE_DIR = Path(
    os.environ.get("COMPASS_USER_PROFILE_HOME")
    or os.environ.get("CODEX_USER_PROFILE_HOME")
    or DEFAULT_BASE_DIR
).expanduser()
VALID_SOURCE_TYPES = {"self_report", "observed", "inferred", "correction"}
VALID_SENSITIVITY = {"low", "private", "sensitive", "intimate", "secret"}
VALID_STATUS = {"active", "pending", "superseded", "retracted", "conflicted"}
SUMMARY_CATEGORIES = {
    "communication_preference",
    "clarification_style",
    "decision_style",
    "domain_familiarity",
    "capability_boundary",
    "common_omission",
    "risk_boundary",
    "privacy_boundary",
    "workflow_preference",
    "correction",
    "anti_bubble_rule",
}
PROFILE_OVERVIEW_SENSITIVITIES = {"low", "private"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def fail(message: str, code: int = 2) -> None:
    print_json({"ok": False, "error": message})
    raise SystemExit(code)


def safe_user_id(user_id: str) -> str:
    user_id = (user_id or "default").strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not user_id or any(ch not in allowed for ch in user_id) or user_id in {".", ".."}:
        fail("Invalid user id. Use letters, digits, dot, underscore, or hyphen only.")
    return user_id


def ensure_private_dir(path: Path, mode: int = 0o700) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, mode)
    except PermissionError:
        pass


def ensure_private_file(path: Path, mode: int = 0o600) -> None:
    if path.exists():
        try:
            os.chmod(path, mode)
        except PermissionError:
            pass


def user_dir(user_id: str) -> Path:
    return BASE_DIR / "users" / safe_user_id(user_id)


def db_file(user_id: str) -> Path:
    return user_dir(user_id) / "profile.sqlite3"


def profile_exists(user_id: str) -> bool:
    return db_file(safe_user_id(user_id)).exists()


def atomic_write_json(path: Path, value: Any) -> None:
    ensure_private_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
        ensure_private_file(path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_registry() -> dict[str, Any]:
    registry = BASE_DIR / "registry.json"
    if not registry.exists():
        return {"version": 1, "users": {}, "updated_at": now()}
    return json.loads(registry.read_text(encoding="utf-8"))


def update_registry(user_id: str, display_name: str | None = None) -> None:
    ensure_private_dir(BASE_DIR)
    registry_path = BASE_DIR / "registry.json"
    registry = load_registry()
    users = registry.setdefault("users", {})
    entry = users.setdefault(user_id, {"created_at": now()})
    entry["display_name"] = display_name or entry.get("display_name") or user_id
    entry["path"] = str(user_dir(user_id))
    entry["updated_at"] = now()
    registry["updated_at"] = now()
    atomic_write_json(registry_path, registry)


def connect(user_id: str) -> sqlite3.Connection:
    user_id = safe_user_id(user_id)
    ensure_private_dir(BASE_DIR)
    root = user_dir(user_id)
    ensure_private_dir(root)
    ensure_private_dir(root / "snapshots")
    ensure_private_dir(root / "proposals")
    ensure_private_dir(root / "exports")
    conn = sqlite3.connect(db_file(user_id), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    create_schema(conn)
    ensure_private_file(db_file(user_id))
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          user_id TEXT PRIMARY KEY,
          display_name TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS aliases (
          alias TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          note TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence_events (
          event_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          session_id TEXT,
          timestamp TEXT NOT NULL,
          summary TEXT NOT NULL,
          raw_excerpt TEXT,
          context TEXT,
          privacy_tags_json TEXT NOT NULL,
          source_ref TEXT,
          actor TEXT,
          extraction_method TEXT
        );
        CREATE TABLE IF NOT EXISTS profile_assertions (
          assertion_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          category TEXT NOT NULL,
          claim TEXT NOT NULL,
          value_json TEXT NOT NULL,
          scope TEXT NOT NULL,
          source_type TEXT NOT NULL,
          confidence REAL NOT NULL,
          sensitivity TEXT NOT NULL,
          status TEXT NOT NULL,
          evidence_ids_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          valid_from TEXT,
          valid_to TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_assertions_user_status
          ON profile_assertions(user_id, status, sensitivity, category);
        CREATE INDEX IF NOT EXISTS idx_assertions_conflict_key
          ON profile_assertions(user_id, category, claim, scope, status);
        CREATE TABLE IF NOT EXISTS update_proposals (
          proposal_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          status TEXT NOT NULL,
          base_profile_hash TEXT NOT NULL,
          candidate_json TEXT NOT NULL,
          reason TEXT,
          conflict_assertion_ids_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          applied_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_proposals_user_status
          ON update_proposals(user_id, status, created_at);
        CREATE TABLE IF NOT EXISTS audit_log (
          log_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          action TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT,
          detail_json TEXT NOT NULL,
          timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS consents (
          consent_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          key TEXT NOT NULL,
          value_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_consents_user_key
          ON consents(user_id, key);
        CREATE TABLE IF NOT EXISTS redactions (
          redaction_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL,
          reason TEXT NOT NULL,
          summary TEXT NOT NULL,
          context TEXT,
          created_at TEXT NOT NULL
        );
        """
    )


def audit(conn: sqlite3.Connection, user_id: str, action: str, target_type: str, target_id: str | None, detail: Any) -> None:
    conn.execute(
        """
        INSERT INTO audit_log(log_id,user_id,action,target_type,target_id,detail_json,timestamp)
        VALUES(?,?,?,?,?,?,?)
        """,
        (str(uuid.uuid4()), user_id, action, target_type, target_id, dump_json(detail), now()),
    )


def init_user(user_id: str, display_name: str | None = None) -> dict[str, Any]:
    user_id = safe_user_id(user_id)
    conn = connect(user_id)
    with conn:
        row = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        ts = now()
        if row:
            conn.execute("UPDATE users SET display_name=?, updated_at=? WHERE user_id=?", (display_name or user_id, ts, user_id))
            created = False
        else:
            conn.execute(
                "INSERT INTO users(user_id,display_name,created_at,updated_at) VALUES(?,?,?,?)",
                (user_id, display_name or user_id, ts, ts),
            )
            created = True
        audit(conn, user_id, "init", "user", user_id, {"created": created, "display_name": display_name or user_id})
    update_registry(user_id, display_name)
    return {"ok": True, "user_id": user_id, "created": created, "db": str(db_file(user_id))}


def parse_json_arg(raw: str | None, file_path: str | None = None, default: Any = None) -> Any:
    if file_path:
        return json.loads(Path(file_path).expanduser().read_text(encoding="utf-8"))
    if raw is None:
        return default
    raw = raw.strip()
    if raw.startswith("@"):
        return json.loads(Path(raw[1:]).expanduser().read_text(encoding="utf-8"))
    return json.loads(raw)


def normalize_candidate(candidate: dict[str, Any], session_summary: str = "") -> dict[str, Any]:
    if not isinstance(candidate, dict):
        fail("Each candidate must be an object.")
    out = dict(candidate)
    required = ["category", "claim", "value"]
    missing = [key for key in required if key not in out or out[key] in (None, "")]
    if missing:
        fail(f"Candidate missing required fields: {', '.join(missing)}")
    out["category"] = str(out["category"]).strip()
    out["claim"] = str(out["claim"]).strip()
    if not isinstance(out["value"], (dict, list)):
        out["value"] = {"summary": str(out["value"])}
    out["scope"] = str(out.get("scope") or "global").strip()
    out["source_type"] = str(out.get("source_type") or "inferred").strip()
    out["sensitivity"] = str(out.get("sensitivity") or "private").strip()
    if out["source_type"] not in VALID_SOURCE_TYPES:
        fail(f"Invalid source_type: {out['source_type']}")
    if out["sensitivity"] not in VALID_SENSITIVITY:
        fail(f"Invalid sensitivity: {out['sensitivity']}")
    try:
        out["confidence"] = float(out.get("confidence", 0.5))
    except (TypeError, ValueError):
        fail("confidence must be a number.")
    out["confidence"] = max(0.0, min(1.0, out["confidence"]))
    evidence = out.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {"summary": str(evidence)}
    evidence.setdefault("summary", session_summary or f"{out['category']}:{out['claim']}")
    evidence.setdefault("context", "current session")
    if "raw_excerpt" in evidence and evidence["raw_excerpt"] is not None:
        evidence["raw_excerpt"] = str(evidence["raw_excerpt"])[:500]
    if out["sensitivity"] != "low":
        evidence.pop("raw_excerpt", None)
    out["evidence"] = evidence
    return out


def value_json(candidate: dict[str, Any]) -> str:
    return dump_json(candidate["value"])


def profile_hash(conn: sqlite3.Connection, user_id: str) -> str:
    rows = conn.execute(
        """
        SELECT category, claim, value_json, scope, source_type, confidence, sensitivity, status, updated_at
        FROM profile_assertions
        WHERE user_id=? AND status='active'
        ORDER BY category, claim, scope, assertion_id
        """,
        (user_id,),
    ).fetchall()
    payload = [dict(row) for row in rows]
    return hashlib.sha256(dump_json(payload).encode("utf-8")).hexdigest()


def conflicts_for(conn: sqlite3.Connection, user_id: str, candidate: dict[str, Any]) -> list[str]:
    rows = conn.execute(
        """
        SELECT assertion_id, value_json
        FROM profile_assertions
        WHERE user_id=? AND category=? AND claim=? AND scope=? AND status='active'
        """,
        (user_id, candidate["category"], candidate["claim"], candidate["scope"]),
    ).fetchall()
    wanted = value_json(candidate)
    return [row["assertion_id"] for row in rows if row["value_json"] != wanted]


def is_safe_auto_apply(candidate: dict[str, Any], conflicts: list[str]) -> bool:
    return (
        candidate["sensitivity"] == "low"
        and candidate["source_type"] in {"self_report", "observed", "correction"}
        and candidate["confidence"] >= 0.75
        and not conflicts
    )


def insert_redaction(conn: sqlite3.Connection, user_id: str, candidate: dict[str, Any], reason: str) -> str:
    redaction_id = str(uuid.uuid4())
    evidence = candidate.get("evidence") or {}
    summary = str(evidence.get("summary") or candidate.get("claim") or "redacted")
    conn.execute(
        "INSERT INTO redactions(redaction_id,user_id,reason,summary,context,created_at) VALUES(?,?,?,?,?,?)",
        (redaction_id, user_id, reason, summary[:500], str(evidence.get("context") or ""), now()),
    )
    audit(conn, user_id, "redact", "redaction", redaction_id, {"reason": reason, "category": candidate.get("category"), "claim": candidate.get("claim")})
    return redaction_id


def insert_assertion(conn: sqlite3.Connection, user_id: str, candidate: dict[str, Any], status: str = "active") -> str:
    if status not in VALID_STATUS:
        fail(f"Invalid assertion status: {status}")
    evidence = candidate.get("evidence") or {}
    event_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO evidence_events(event_id,user_id,session_id,timestamp,summary,raw_excerpt,context,privacy_tags_json,source_ref,actor,extraction_method)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            event_id,
            user_id,
            str(evidence.get("session_id") or ""),
            now(),
            str(evidence.get("summary") or candidate["claim"])[:1000],
            evidence.get("raw_excerpt"),
            str(evidence.get("context") or ""),
            dump_json(evidence.get("privacy_tags") or [candidate["sensitivity"]]),
            str(evidence.get("source_ref") or ""),
            str(evidence.get("actor") or "user"),
            str(evidence.get("extraction_method") or "agent"),
        ),
    )
    assertion_id = str(uuid.uuid4())
    ts = now()
    conn.execute(
        """
        INSERT INTO profile_assertions(
          assertion_id,user_id,category,claim,value_json,scope,source_type,confidence,sensitivity,status,
          evidence_ids_json,created_at,updated_at,valid_from,valid_to
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            assertion_id,
            user_id,
            candidate["category"],
            candidate["claim"],
            value_json(candidate),
            candidate["scope"],
            candidate["source_type"],
            candidate["confidence"],
            candidate["sensitivity"],
            status,
            dump_json([event_id]),
            ts,
            ts,
            ts if status == "active" else None,
            None,
        ),
    )
    audit(conn, user_id, "assertion_add", "assertion", assertion_id, {"status": status, "category": candidate["category"], "claim": candidate["claim"]})
    return assertion_id


def create_proposal(
    conn: sqlite3.Connection,
    user_id: str,
    candidates: list[dict[str, Any]],
    reason: str,
    conflicts: list[str] | None = None,
) -> str:
    proposal_id = str(uuid.uuid4())
    ts = now()
    conn.execute(
        """
        INSERT INTO update_proposals(
          proposal_id,user_id,status,base_profile_hash,candidate_json,reason,conflict_assertion_ids_json,created_at,updated_at,applied_at
        ) VALUES(?,?,?,?,?,?,?,?,?,NULL)
        """,
        (
            proposal_id,
            user_id,
            "pending",
            profile_hash(conn, user_id),
            dump_json(candidates),
            reason,
            dump_json(conflicts or []),
            ts,
            ts,
        ),
    )
    audit(conn, user_id, "proposal_create", "proposal", proposal_id, {"count": len(candidates), "reason": reason, "conflicts": conflicts or []})
    return proposal_id


def command_update_from_session(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    init_user(user_id, args.display_name)
    candidates_raw = parse_json_arg(args.candidate_json, args.candidate_file, [])
    if not isinstance(candidates_raw, list):
        fail("candidate-json must be a JSON array.")
    conn = connect(user_id)
    applied: list[str] = []
    proposed: list[str] = []
    redacted: list[str] = []
    skipped: list[str] = []
    with conn:
        for raw in candidates_raw:
            candidate = normalize_candidate(raw, args.session_summary or "")
            if candidate["sensitivity"] == "secret":
                redacted.append(insert_redaction(conn, user_id, candidate, "secret content is never stored"))
                continue
            conflicts = conflicts_for(conn, user_id, candidate)
            if args.auto_apply_safe and is_safe_auto_apply(candidate, conflicts):
                applied.append(insert_assertion(conn, user_id, candidate, "active"))
            elif args.propose:
                proposed.append(create_proposal(conn, user_id, [candidate], args.reason or "requires confirmation", conflicts))
            else:
                skipped.append(f"{candidate['category']}:{candidate['claim']}")
        audit(conn, user_id, "update_from_session", "user", user_id, {"applied": applied, "proposed": proposed, "redacted": redacted, "skipped": skipped})
    update_registry(user_id, args.display_name)
    return {"ok": True, "user_id": user_id, "applied": applied, "proposals": proposed, "redactions": redacted, "skipped": skipped, "profile_hash": profile_hash(conn, user_id)}


def row_to_assertion(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "assertion_id": row["assertion_id"],
        "category": row["category"],
        "claim": row["claim"],
        "value": json.loads(row["value_json"]),
        "scope": row["scope"],
        "source_type": row["source_type"],
        "confidence": row["confidence"],
        "sensitivity": row["sensitivity"],
        "status": row["status"],
        "evidence_ids": json.loads(row["evidence_ids_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "valid_from": row["valid_from"],
        "valid_to": row["valid_to"],
    }


def read_view(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        if args.view == "pending":
            return {"ok": True, "user_id": user_id, "profile_exists": False, "proposals": []}
        return {
            "ok": True,
            "user_id": user_id,
            "profile_exists": False,
            "view": args.view,
            "profile_hash": None,
            "items": [],
            "anti_bubble": [
                "未找到本地画像；按当前 session 和任务证据澄清。",
                "重大或不可逆动作仍需确认。",
            ] if args.view == "clarification_summary" else [],
        }
    conn = connect(user_id)
    view = args.view
    if view == "clarification_summary":
        rows = conn.execute(
            """
            SELECT * FROM profile_assertions
            WHERE user_id=? AND status='active' AND sensitivity='low'
            ORDER BY category, updated_at DESC, claim
            """,
            (user_id,),
        ).fetchall()
        items = [row_to_assertion(row) for row in rows if row["category"] in SUMMARY_CATEGORIES]
        return {
            "ok": True,
            "user_id": user_id,
            "view": view,
            "profile_hash": profile_hash(conn, user_id),
            "items": items,
            "anti_bubble": [
                "当前 session 明确要求优先于历史画像。",
                "重大或不可逆动作仍需确认。",
                "至少检查一个不符合既有画像的可能解释。",
            ],
        }
    if view == "profile_overview":
        rows = conn.execute(
            """
            SELECT * FROM profile_assertions
            WHERE user_id=? AND status='active' AND sensitivity IN ('low','private')
            ORDER BY category, updated_at DESC, claim
            """,
            (user_id,),
        ).fetchall()
        items = []
        for row in rows:
            item = row_to_assertion(row)
            item.pop("evidence_ids", None)
            items.append(item)
        return {
            "ok": True,
            "user_id": user_id,
            "view": view,
            "profile_hash": profile_hash(conn, user_id),
            "items": items,
            "omitted": {
                "sensitivities": sorted(VALID_SENSITIVITY - PROFILE_OVERVIEW_SENSITIVITIES),
                "reason": "profile_overview 只展示 low/private active 断言，避免日常查看时扩散更敏感内容。",
            },
        }
    if view == "full":
        rows = conn.execute(
            "SELECT * FROM profile_assertions WHERE user_id=? ORDER BY status, category, updated_at DESC",
            (user_id,),
        ).fetchall()
        return {"ok": True, "user_id": user_id, "view": view, "profile_hash": profile_hash(conn, user_id), "items": [row_to_assertion(row) for row in rows]}
    if view == "pending":
        return proposal_list(args)
    fail(f"Unknown view: {view}")


def proposal_list(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        return {"ok": True, "user_id": user_id, "profile_exists": False, "proposals": []}
    conn = connect(user_id)
    statuses = getattr(args, "status", None) or ["pending", "conflicted"]
    placeholders = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"SELECT * FROM update_proposals WHERE user_id=? AND status IN ({placeholders}) ORDER BY created_at DESC",
        [user_id, *statuses],
    ).fetchall()
    proposals = []
    for row in rows:
        proposals.append(
            {
                "proposal_id": row["proposal_id"],
                "status": row["status"],
                "base_profile_hash": row["base_profile_hash"],
                "current_profile_hash": profile_hash(conn, user_id),
                "candidates": json.loads(row["candidate_json"]),
                "reason": row["reason"],
                "conflict_assertion_ids": json.loads(row["conflict_assertion_ids_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "applied_at": row["applied_at"],
            }
        )
    return {"ok": True, "user_id": user_id, "proposals": proposals}


def proposal_apply(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        fail("Profile does not exist.", 4)
    conn = connect(user_id)
    with conn:
        row = conn.execute(
            "SELECT * FROM update_proposals WHERE user_id=? AND proposal_id=?",
            (user_id, args.proposal_id),
        ).fetchone()
        if not row:
            fail("Proposal not found.", 4)
        if row["status"] not in {"pending", "conflicted"}:
            fail(f"Proposal is not applicable: {row['status']}", 4)
        current_hash = profile_hash(conn, user_id)
        if row["base_profile_hash"] != current_hash and not args.allow_stale:
            conn.execute("UPDATE update_proposals SET status='conflicted', updated_at=? WHERE proposal_id=?", (now(), args.proposal_id))
            audit(conn, user_id, "proposal_conflict", "proposal", args.proposal_id, {"base_profile_hash": row["base_profile_hash"], "current_profile_hash": current_hash})
            return {"ok": False, "user_id": user_id, "proposal_id": args.proposal_id, "status": "conflicted", "error": "Profile changed since proposal was created. Re-review or pass --allow-stale."}
        conflict_ids = json.loads(row["conflict_assertion_ids_json"])
        for assertion_id in conflict_ids:
            conn.execute(
                "UPDATE profile_assertions SET status='superseded', updated_at=?, valid_to=? WHERE user_id=? AND assertion_id=? AND status='active'",
                (now(), now(), user_id, assertion_id),
            )
        assertion_ids = []
        for raw in json.loads(row["candidate_json"]):
            candidate = normalize_candidate(raw)
            if candidate["sensitivity"] == "secret":
                insert_redaction(conn, user_id, candidate, "secret content is never stored")
                continue
            assertion_ids.append(insert_assertion(conn, user_id, candidate, "active"))
        conn.execute(
            "UPDATE update_proposals SET status='applied', updated_at=?, applied_at=? WHERE proposal_id=?",
            (now(), now(), args.proposal_id),
        )
        audit(conn, user_id, "proposal_apply", "proposal", args.proposal_id, {"assertion_ids": assertion_ids, "superseded": conflict_ids})
    return {"ok": True, "user_id": user_id, "proposal_id": args.proposal_id, "assertion_ids": assertion_ids, "profile_hash": profile_hash(conn, user_id)}


def proposal_reject(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        fail("Profile does not exist.", 4)
    conn = connect(user_id)
    with conn:
        conn.execute(
            "UPDATE update_proposals SET status='rejected', updated_at=? WHERE user_id=? AND proposal_id=? AND status IN ('pending','conflicted')",
            (now(), user_id, args.proposal_id),
        )
        audit(conn, user_id, "proposal_reject", "proposal", args.proposal_id, {"note": args.note or ""})
    return {"ok": True, "user_id": user_id, "proposal_id": args.proposal_id}


def assertion_add(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    init_user(user_id, None)
    value = parse_json_arg(args.value_json, args.value_file, None)
    candidate = normalize_candidate(
        {
            "category": args.category,
            "claim": args.claim,
            "value": value,
            "scope": args.scope,
            "source_type": args.source_type,
            "confidence": args.confidence,
            "sensitivity": args.sensitivity,
            "evidence": {"summary": args.evidence_summary or "manual assertion", "context": args.context or "manual"},
        }
    )
    conn = connect(user_id)
    with conn:
        if candidate["sensitivity"] == "secret":
            rid = insert_redaction(conn, user_id, candidate, "secret content is never stored")
            return {"ok": True, "user_id": user_id, "redaction_id": rid}
        assertion_id = insert_assertion(conn, user_id, candidate, args.status)
    return {"ok": True, "user_id": user_id, "assertion_id": assertion_id}


def correct(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        fail("Profile does not exist.", 4)
    conn = connect(user_id)
    replacement = parse_json_arg(args.replacement_json, args.replacement_file, None)
    with conn:
        row = conn.execute("SELECT * FROM profile_assertions WHERE user_id=? AND assertion_id=?", (user_id, args.assertion_id)).fetchone()
        if not row:
            fail("Assertion not found.", 4)
        conn.execute(
            "UPDATE profile_assertions SET status='retracted', updated_at=?, valid_to=? WHERE user_id=? AND assertion_id=?",
            (now(), now(), user_id, args.assertion_id),
        )
        new_assertion_id = None
        if replacement is not None:
            candidate = normalize_candidate(
                {
                    "category": row["category"],
                    "claim": row["claim"],
                    "value": replacement,
                    "scope": row["scope"],
                    "source_type": "correction",
                    "confidence": 1.0,
                    "sensitivity": row["sensitivity"],
                    "evidence": {"summary": args.note, "context": "user correction"},
                }
            )
            new_assertion_id = insert_assertion(conn, user_id, candidate, "active")
        audit(conn, user_id, "assertion_correct", "assertion", args.assertion_id, {"note": args.note, "replacement_assertion_id": new_assertion_id})
    return {"ok": True, "user_id": user_id, "retracted": args.assertion_id, "replacement_assertion_id": new_assertion_id}


def delete_assertion(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        fail("Profile does not exist.", 4)
    conn = connect(user_id)
    with conn:
        row = conn.execute("SELECT evidence_ids_json FROM profile_assertions WHERE user_id=? AND assertion_id=?", (user_id, args.assertion_id)).fetchone()
        if not row:
            fail("Assertion not found.", 4)
        evidence_ids = json.loads(row["evidence_ids_json"])
        if args.hard:
            conn.execute("DELETE FROM profile_assertions WHERE user_id=? AND assertion_id=?", (user_id, args.assertion_id))
            for event_id in evidence_ids:
                conn.execute("DELETE FROM evidence_events WHERE user_id=? AND event_id=?", (user_id, event_id))
            action = "assertion_hard_delete"
        else:
            conn.execute(
                "UPDATE profile_assertions SET status='retracted', updated_at=?, valid_to=? WHERE user_id=? AND assertion_id=?",
                (now(), now(), user_id, args.assertion_id),
            )
            action = "assertion_retract"
        audit(conn, user_id, action, "assertion", args.assertion_id, {"hard": args.hard, "note": args.note or ""})
    return {"ok": True, "user_id": user_id, "assertion_id": args.assertion_id, "hard": args.hard}


def search(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        return {"ok": True, "user_id": user_id, "profile_exists": False, "query": args.query, "items": []}
    conn = connect(user_id)
    like = f"%{args.query}%"
    rows = conn.execute(
        """
        SELECT * FROM profile_assertions
        WHERE user_id=? AND (category LIKE ? OR claim LIKE ? OR value_json LIKE ? OR scope LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (user_id, like, like, like, like, args.limit),
    ).fetchall()
    return {"ok": True, "user_id": user_id, "query": args.query, "items": [row_to_assertion(row) for row in rows]}


def export_profile(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    if not profile_exists(user_id):
        fail("Profile does not exist.", 4)
    conn = connect(user_id)
    if args.redacted:
        rows = conn.execute(
            "SELECT * FROM profile_assertions WHERE user_id=? AND sensitivity='low' ORDER BY category, claim",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM profile_assertions WHERE user_id=? ORDER BY category, claim", (user_id,)).fetchall()
    payload = {
        "user_id": user_id,
        "exported_at": now(),
        "redacted": args.redacted,
        "profile_hash": profile_hash(conn, user_id),
        "items": [row_to_assertion(row) for row in rows],
    }
    out = Path(args.output).expanduser() if args.output else user_dir(user_id) / "exports" / f"profile-{int(time.time())}.json"
    atomic_write_json(out, payload)
    return {"ok": True, "user_id": user_id, "output": str(out), "redacted": args.redacted, "count": len(payload["items"])}


def validate(args: argparse.Namespace) -> dict[str, Any]:
    user_id = safe_user_id(args.user)
    init_user(user_id, None)
    conn = connect(user_id)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    db = db_file(user_id)
    base_mode = oct(BASE_DIR.stat().st_mode & 0o777)
    db_mode = oct(db.stat().st_mode & 0o777)
    rows = conn.execute("SELECT assertion_id,evidence_ids_json FROM profile_assertions WHERE user_id=?", (user_id,)).fetchall()
    orphan_refs: list[dict[str, str]] = []
    for row in rows:
        for event_id in json.loads(row["evidence_ids_json"]):
            found = conn.execute("SELECT 1 FROM evidence_events WHERE user_id=? AND event_id=?", (user_id, event_id)).fetchone()
            if not found:
                orphan_refs.append({"assertion_id": row["assertion_id"], "event_id": event_id})
    return {
        "ok": integrity == "ok" and not orphan_refs,
        "user_id": user_id,
        "integrity_check": integrity,
        "journal_mode": mode,
        "base_dir": str(BASE_DIR),
        "base_mode": base_mode,
        "db": str(db),
        "db_mode": db_mode,
        "orphan_evidence_refs": orphan_refs,
        "profile_hash": profile_hash(conn, user_id),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local user-profile store")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--user", default="default")
    p.add_argument("--display-name")
    p.set_defaults(func=lambda args: init_user(args.user, args.display_name))

    p = sub.add_parser("read")
    p.add_argument("--user", default="default")
    p.add_argument("--view", choices=["clarification_summary", "profile_overview", "full", "pending"], default="clarification_summary")
    p.set_defaults(func=read_view)

    p = sub.add_parser("update-from-session")
    p.add_argument("--user", default="default")
    p.add_argument("--display-name")
    p.add_argument("--session-summary", default="")
    p.add_argument("--candidate-json")
    p.add_argument("--candidate-file")
    p.add_argument("--reason")
    p.add_argument("--auto-apply-safe", action="store_true")
    p.add_argument("--propose", action="store_true", default=True)
    p.set_defaults(func=command_update_from_session)

    p = sub.add_parser("proposal-create")
    p.add_argument("--user", default="default")
    p.add_argument("--candidate-json")
    p.add_argument("--candidate-file")
    p.add_argument("--reason", default="manual proposal")
    p.set_defaults(func=lambda args: command_update_from_session(argparse.Namespace(**vars(args), display_name=None, session_summary="", auto_apply_safe=False, propose=True)))

    p = sub.add_parser("proposal-list")
    p.add_argument("--user", default="default")
    p.add_argument("--status", action="append")
    p.set_defaults(func=proposal_list)

    p = sub.add_parser("proposal-apply")
    p.add_argument("--user", default="default")
    p.add_argument("--proposal-id", required=True)
    p.add_argument("--allow-stale", action="store_true")
    p.set_defaults(func=proposal_apply)

    p = sub.add_parser("proposal-reject")
    p.add_argument("--user", default="default")
    p.add_argument("--proposal-id", required=True)
    p.add_argument("--note")
    p.set_defaults(func=proposal_reject)

    p = sub.add_parser("assertion-add")
    p.add_argument("--user", default="default")
    p.add_argument("--category", required=True)
    p.add_argument("--claim", required=True)
    p.add_argument("--value-json")
    p.add_argument("--value-file")
    p.add_argument("--scope", default="global")
    p.add_argument("--source-type", choices=sorted(VALID_SOURCE_TYPES), default="self_report")
    p.add_argument("--confidence", type=float, default=0.9)
    p.add_argument("--sensitivity", choices=sorted(VALID_SENSITIVITY), default="low")
    p.add_argument("--status", choices=sorted(VALID_STATUS), default="active")
    p.add_argument("--evidence-summary")
    p.add_argument("--context")
    p.set_defaults(func=assertion_add)

    p = sub.add_parser("correct")
    p.add_argument("--user", default="default")
    p.add_argument("--assertion-id", required=True)
    p.add_argument("--note", required=True)
    p.add_argument("--replacement-json")
    p.add_argument("--replacement-file")
    p.set_defaults(func=correct)

    p = sub.add_parser("delete")
    p.add_argument("--user", default="default")
    p.add_argument("--assertion-id", required=True)
    p.add_argument("--note")
    p.add_argument("--hard", action="store_true")
    p.set_defaults(func=delete_assertion)

    p = sub.add_parser("search")
    p.add_argument("--user", default="default")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=search)

    p = sub.add_parser("export")
    p.add_argument("--user", default="default")
    p.add_argument("--output")
    p.add_argument("--redacted", action="store_true", default=True)
    p.add_argument("--full", dest="redacted", action="store_false")
    p.set_defaults(func=export_profile)

    p = sub.add_parser("validate")
    p.add_argument("--user", default="default")
    p.set_defaults(func=validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print_json(result)
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
