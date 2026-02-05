#!/usr/bin/env python3
"""Soul Forge additive upgrade generator.

Non-destructive by default:
- Reads an existing SOUL.md (base)
- Reads an addendum markdown file
- Writes timestamped artifacts under outputs/
- Writes a seal JSON under soul-seal/
- Prints a unified diff between base and combined
- Only overwrites SOUL.md when --apply is provided (and makes a backup)
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime


def sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # never silently clobber generated artifacts
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.write_text(content, encoding="utf-8")


def now_ts() -> str:
    # sortable, filesystem-friendly
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def build_combined(base: str, addendum: str, ts: str) -> str:
    base = base.rstrip() + "\n"
    addendum = addendum.strip() + "\n"
    separator = "\n\n---\n\n"
    header = f"# SOUL Addendum ({ts})\n\n"
    return base + separator + header + addendum


def unified_diff(a: str, b: str, fromfile: str, tofile: str) -> str:
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    diff = difflib.unified_diff(a_lines, b_lines, fromfile=fromfile, tofile=tofile)
    return "".join(diff)


def main() -> int:
    ap = argparse.ArgumentParser(prog="soulforge-additive", add_help=True)
    ap.add_argument(
        "--soul-path",
        default="SOUL.md",
        help="Path to the base SOUL.md (default: ./SOUL.md)",
    )
    ap.add_argument(
        "--addendum-path",
        required=True,
        help="Path to a markdown file containing ONLY the addendum content",
    )
    ap.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory for generated markdown outputs (default: ./outputs)",
    )
    ap.add_argument(
        "--seal-dir",
        default="soul-seal",
        help="Directory for seal JSON outputs (default: ./soul-seal)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Overwrite SOUL.md with the combined result (creates backup first)",
    )

    args = ap.parse_args()

    ts = now_ts()

    soul_path = Path(args.soul_path)
    addendum_path = Path(args.addendum_path)
    outputs_dir = Path(args.outputs_dir)
    seal_dir = Path(args.seal_dir)

    if not soul_path.exists():
        raise FileNotFoundError(f"Base SOUL file not found: {soul_path}")
    if not addendum_path.exists():
        raise FileNotFoundError(f"Addendum file not found: {addendum_path}")

    base_text = read_text(soul_path)
    addendum_text = read_text(addendum_path)

    combined_text = build_combined(base_text, addendum_text, ts)

    addendum_out = outputs_dir / f"SOUL.ADDENDUM.{ts}.md"
    combined_out = outputs_dir / f"SOUL.COMBINED.{ts}.md"
    seal_out = seal_dir / f"{ts}.json"

    write_text(addendum_out, addendum_text.rstrip() + "\n")
    write_text(combined_out, combined_text)

    seal = {
        "timestamp": ts,
        "inputs": {
            "soul_path": str(soul_path),
            "addendum_path": str(addendum_path),
            "outputs_dir": str(outputs_dir),
            "seal_dir": str(seal_dir),
            "apply": bool(args.apply),
        },
        "hashes": {
            "base_sha256": sha256_text(base_text),
            "addendum_sha256": sha256_text(addendum_text),
            "combined_sha256": sha256_text(combined_text),
        },
        "artifacts": {
            "addendum_out": str(addendum_out),
            "combined_out": str(combined_out),
        },
    }

    seal_out.parent.mkdir(parents=True, exist_ok=True)
    if seal_out.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {seal_out}")
    seal_out.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    diff_text = unified_diff(base_text, combined_text, fromfile=str(soul_path), tofile=f"SOUL.md (combined {ts})")
    if diff_text.strip():
        print(diff_text)
    else:
        print("(no diff)")

    if args.apply:
        backup_path = soul_path.with_name(f"SOUL.backup.{ts}.md")
        if backup_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing backup: {backup_path}")
        backup_path.write_text(base_text, encoding="utf-8")
        soul_path.write_text(combined_text, encoding="utf-8")
        print(f"\nApplied: overwrote {soul_path} (backup at {backup_path})")
    else:
        print("\nNot applied. Re-run with --apply to overwrite SOUL.md (a backup will be created).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
