"""Non-destructive SOUL.md addendum generator.

Writes timestamped artifacts and a hash seal. Overwrites the base file
only when apply is requested, and writes a backup first.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


def sha256_text(text: str) -> str:
    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def now_ts(now: datetime | None = None) -> str:
    """Sortable, filesystem-friendly local timestamp.

    Microseconds are included so two writes in the same second (preview,
    then apply) do not collide. Tests can still inject a fixed ``now``.
    """

    moment = datetime.now() if now is None else now
    return moment.strftime("%Y%m%d-%H%M%S-%f")


def build_combined(base: str, addendum: str, ts: str) -> str:
    base_norm = base.rstrip() + "\n"
    addendum_norm = addendum.strip() + "\n"
    separator = "\n\n---\n\n"
    header = f"# SOUL Addendum ({ts})\n\n"
    return base_norm + separator + header + addendum_norm


def unified_diff(before: str, after: str, fromfile: str, tofile: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
    )
    return "".join(diff)


@dataclass(frozen=True)
class AddendumResult:
    timestamp: str
    base_text: str
    addendum_text: str
    combined_text: str
    diff_text: str
    addendum_out: Path
    combined_out: Path
    seal_out: Path
    applied: bool
    backup_path: Path | None


def run_addendum(
    *,
    soul_path: Path,
    addendum_text: str,
    outputs_dir: Path,
    seal_dir: Path,
    apply: bool,
    extra_inputs: Mapping[str, object] | None = None,
    ts: str | None = None,
    addendum_path_label: str | None = None,
) -> AddendumResult:
    """Write artifacts and, when ``apply`` is set, replace ``soul_path``.

    Refuses to overwrite an existing artifact, seal, or backup.
    """

    if not soul_path.exists():
        raise FileNotFoundError(f"Base SOUL file not found: {soul_path}")
    if not addendum_text.strip():
        raise ValueError("Addendum text is empty")

    stamp = now_ts() if ts is None else ts
    base_text = read_text(soul_path)
    combined_text = build_combined(base_text, addendum_text, stamp)
    addendum_out = outputs_dir / f"SOUL.ADDENDUM.{stamp}.md"
    combined_out = outputs_dir / f"SOUL.COMBINED.{stamp}.md"
    seal_out = seal_dir / f"{stamp}.json"
    for path in (addendum_out, combined_out, seal_out):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {path}")

    stored_addendum = addendum_text.rstrip() + "\n"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    seal_dir.mkdir(parents=True, exist_ok=True)
    addendum_out.write_text(stored_addendum, encoding="utf-8")
    combined_out.write_text(combined_text, encoding="utf-8")

    inputs: dict[str, object] = {
        "soul_path": str(soul_path),
        "outputs_dir": str(outputs_dir),
        "seal_dir": str(seal_dir),
        "apply": apply,
    }
    if addendum_path_label is not None:
        inputs["addendum_path"] = addendum_path_label
    if extra_inputs:
        inputs.update(dict(extra_inputs))

    seal = {
        "timestamp": stamp,
        "inputs": inputs,
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
    seal_out.write_text(
        json.dumps(seal, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    diff_text = unified_diff(
        base_text,
        combined_text,
        fromfile=str(soul_path),
        tofile=f"SOUL.md (combined {stamp})",
    )
    backup_path: Path | None = None
    if apply:
        backup_path = soul_path.with_name(f"SOUL.backup.{stamp}.md")
        if backup_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing backup: {backup_path}")
        backup_path.write_text(base_text, encoding="utf-8")
        soul_path.write_text(combined_text, encoding="utf-8")

    return AddendumResult(
        timestamp=stamp,
        base_text=base_text,
        addendum_text=addendum_text,
        combined_text=combined_text,
        diff_text=diff_text,
        addendum_out=addendum_out,
        combined_out=combined_out,
        seal_out=seal_out,
        applied=apply,
        backup_path=backup_path,
    )


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--soul-path",
        default="SOUL.md",
        help="Path to the base SOUL.md (default: ./SOUL.md)",
    )
    parser.add_argument(
        "--addendum-path",
        required=True,
        help="Path to a markdown file containing ONLY the addendum content",
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory for generated markdown outputs (default: ./outputs)",
    )
    parser.add_argument(
        "--seal-dir",
        default="soul-seal",
        help="Directory for seal JSON outputs (default: ./soul-seal)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Overwrite SOUL.md with the combined result (creates backup first)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soulforge-additive")
    add_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    soul_path = Path(args.soul_path)
    addendum_path = Path(args.addendum_path)
    try:
        if not addendum_path.exists():
            raise FileNotFoundError(f"Addendum file not found: {addendum_path}")
        result = run_addendum(
            soul_path=soul_path,
            addendum_text=read_text(addendum_path),
            outputs_dir=Path(args.outputs_dir),
            seal_dir=Path(args.seal_dir),
            apply=bool(args.apply),
            addendum_path_label=str(addendum_path),
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if result.diff_text.strip():
        print(result.diff_text, end="" if result.diff_text.endswith("\n") else "\n")
    else:
        print("(no diff)")
    if result.applied and result.backup_path is not None:
        print(
            f"\nApplied: overwrote {soul_path} (backup at {result.backup_path})"
        )
    else:
        print(
            "\nNot applied. Re-run with --apply to overwrite SOUL.md "
            "(a backup will be created)."
        )
    return 0
