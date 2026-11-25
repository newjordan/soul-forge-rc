from __future__ import annotations

import json
from pathlib import Path

import pytest

from soulforge.additive import main, run_addendum, sha256_text


def test_preview_writes_artifacts_and_leaves_the_base_file(tmp_path: Path) -> None:
    soul = tmp_path / "SOUL.md"
    original = "# Soul\n\nBe brief.\n"
    soul.write_text(original, encoding="utf-8")
    addendum = tmp_path / "add.md"
    addendum.write_text("Be warmer when it helps.\n", encoding="utf-8")
    code = main(
        [
            "--soul-path",
            str(soul),
            "--addendum-path",
            str(addendum),
            "--outputs-dir",
            str(tmp_path / "outputs"),
            "--seal-dir",
            str(tmp_path / "seals"),
        ]
    )
    assert code == 0
    assert soul.read_text(encoding="utf-8") == original
    seal_path = next((tmp_path / "seals").glob("*.json"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    assert seal["inputs"]["apply"] is False
    assert seal["hashes"]["base_sha256"] == sha256_text(original)
    combined = Path(seal["artifacts"]["combined_out"]).read_text(encoding="utf-8")
    assert "# SOUL Addendum" in combined
    assert "Be warmer when it helps." in combined
    assert "Be brief." in combined


def test_apply_backs_up_then_overwrites(tmp_path: Path) -> None:
    soul = tmp_path / "SOUL.md"
    soul.write_text("# Soul\n\nBe brief.\n", encoding="utf-8")
    addendum = tmp_path / "add.md"
    addendum.write_text("Ask before external actions.\n", encoding="utf-8")
    code = main(
        [
            "--soul-path",
            str(soul),
            "--addendum-path",
            str(addendum),
            "--outputs-dir",
            str(tmp_path / "outputs"),
            "--seal-dir",
            str(tmp_path / "seals"),
            "--apply",
        ]
    )
    assert code == 0
    updated = soul.read_text(encoding="utf-8")
    assert "Ask before external actions." in updated
    backups = list(tmp_path.glob("SOUL.backup.*.md"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "# Soul\n\nBe brief.\n"


def test_missing_files_return_exit_code_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing.md"
    code = main(
        [
            "--soul-path",
            str(tmp_path / "SOUL.md"),
            "--addendum-path",
            str(missing),
        ]
    )
    assert code == 2
    assert "not found" in capsys.readouterr().err.lower()


def test_refuses_to_clobber_an_existing_artifact(tmp_path: Path) -> None:
    soul = tmp_path / "SOUL.md"
    soul.write_text("# Soul\n", encoding="utf-8")
    outputs = tmp_path / "outputs"
    seals = tmp_path / "seals"
    run_addendum(
        soul_path=soul,
        addendum_text="First.\n",
        outputs_dir=outputs,
        seal_dir=seals,
        apply=False,
        ts="20260101-000000",
    )
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run_addendum(
            soul_path=soul,
            addendum_text="Second.\n",
            outputs_dir=outputs,
            seal_dir=seals,
            apply=False,
            ts="20260101-000000",
        )
    assert soul.read_text(encoding="utf-8") == "# Soul\n"
