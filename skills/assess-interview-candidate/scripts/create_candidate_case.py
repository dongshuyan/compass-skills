#!/usr/bin/env python3
"""Create a new, pseudonymous candidate-assessment workspace."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


DIRECTORIES = (
    "input",
    "normalized",
    "research",
    "research/role-current",
    "research/candidate-professional",
    "research/methods",
    "models",
    "interview",
    "output",
    "audit",
)


def fail(message: str, code: int = 2) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return code


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ValueError("--role-slug must contain at least one ASCII letter or digit")
    return slug[:40].rstrip("-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a unique pseudonymous candidate case below a user-selected root. "
            "The command never reuses or overwrites an existing case directory."
        )
    )
    parser.add_argument("--root", required=True, type=Path, help="Approved parent directory for candidate cases")
    parser.add_argument(
        "--role-slug",
        required=True,
        help="Non-identifying role label, for example ai-engineer (candidate names are forbidden)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        role_slug = slugify(args.role_slug)
        root = args.root.expanduser()
        if root.exists() and root.is_symlink():
            return fail("--root must not be a symbolic link")
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            return fail("--root is not a directory")
        root = root.resolve(strict=True)

        local_now = datetime.now().astimezone()
        timestamp = local_now.strftime("%Y%m%d-%H%M%S")
        case_dir: Path | None = None
        case_id = ""
        for _ in range(20):
            case_id = f"{timestamp}-{role_slug}-{secrets.token_hex(4)}"
            candidate = root / case_id
            try:
                candidate.mkdir(mode=0o700, exist_ok=False)
            except FileExistsError:
                continue
            case_dir = candidate
            break
        if case_dir is None:
            return fail("could not allocate a unique case directory", 1)

        for relative in DIRECTORIES:
            (case_dir / relative).mkdir(mode=0o700, parents=True, exist_ok=False)

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        manifest = {
            "schema_version": "1.0",
            "case_id": case_id,
            "role_slug": role_slug,
            "created_at": created_at,
            "case_id_local_timezone": local_now.tzname(),
            "case_id_local_utc_offset": local_now.strftime("%z"),
            "pseudonymous": True,
            "candidate_name_in_path": False,
            "case_directory": str(case_dir),
            "directories": list(DIRECTORIES),
        }
        manifest_path = case_dir / "audit" / "run-manifest.json"
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        manifest_path.chmod(0o600)

        print(json.dumps({"ok": True, "case_dir": str(case_dir), "case_id": case_id}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        return fail(str(exc), 1)


if __name__ == "__main__":
    raise SystemExit(main())
