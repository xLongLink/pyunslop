import os
import pytest
import subprocess
from pathlib import Path
from pyunslop import find_python_files
from pytest_mock import MockerFixture


def test_discovery_excludes_generated_files_and_deduplicates(tmp_path: Path) -> None:
    """Skip generated directories unless an explicit file path requests them."""
    source = tmp_path / "source.py"
    source.touch()
    (tmp_path / "notes.txt").touch()
    excluded = tmp_path / ".venv"
    excluded.mkdir()
    hidden_source = excluded / "dependency.py"
    hidden_source.touch()

    # Act / Assert: overlapping project paths must not duplicate source files.
    assert list(find_python_files([tmp_path, source])) == [source]
    assert list(find_python_files([hidden_source])) == [hidden_source]


def test_missing_discovery_path_raises(tmp_path: Path) -> None:
    """Report a missing discovery root rather than silently skipping it."""
    with pytest.raises(FileNotFoundError, match="missing"):
        list(find_python_files([tmp_path / "missing"]))


def test_git_ignored_files_are_skipped(tmp_path: Path) -> None:
    """Use Ruff's handling of nested ignores and negated patterns for native scans."""
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored.py\ngenerated/*\n!generated/keep.py\n")
    ignored = tmp_path / "ignored.py"
    ignored.touch()
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "skip.py").touch()
    kept = tmp_path / "generated" / "keep.py"
    kept.touch()

    # Nested ignore files and negated parent rules must both be honored.
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / ".gitignore").write_text("skip.py\n")
    (tmp_path / "nested" / "skip.py").touch()
    assert list(find_python_files([tmp_path])) == [kept]
    assert list(find_python_files([ignored])) == [ignored]


def test_discovery_timeout_is_reported(tmp_path: Path, mocker: MockerFixture) -> None:
    """Apply the same process timeout to discovery and lint execution."""
    mocker.patch("pyunslop.ruff.subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 120))
    with pytest.raises(RuntimeError, match="Ruff timed out"):
        list(find_python_files([tmp_path]))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes are unavailable")
def test_special_files_are_rejected(tmp_path: Path, mocker: MockerFixture) -> None:
    """Reject a named pipe before invoking Ruff or attempting to open it."""
    pipe = tmp_path / "pipe.py"
    os.mkfifo(pipe)
    run = mocker.patch("pyunslop.discovery.run_ruff")
    with pytest.raises(OSError, match="regular file or directory"):
        list(find_python_files([pipe]))
    run.assert_not_called()


def test_repeated_directory_roots_are_scanned_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """Cache directory identities without losing explicit-file bypass behavior."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "example.py"
    source.touch()
    run = mocker.patch("pyunslop.discovery.run_ruff", return_value=f"{source}\n")
    assert list(find_python_files([Path(), tmp_path, Path(), source])) == [Path("example.py")]
    run.assert_called_once()


@pytest.mark.parametrize("separator", ["\n", "\r"])
def test_newline_names_are_rejected(tmp_path: Path, separator: str) -> None:
    """Do not interpret portions of a file name as separate discovered paths."""
    source = tmp_path / f"first{separator}second.py"
    source.touch()
    with pytest.raises(RuntimeError, match="[Nn]ewline-containing paths are unsupported"):
        list(find_python_files([tmp_path]))
    with pytest.raises(RuntimeError, match="Newline-containing paths are unsupported"):
        list(find_python_files([source]))


def test_ambiguous_existing_prefix_is_rejected(tmp_path: Path, mocker: MockerFixture) -> None:
    """A valid truncated prefix must not silently hide an unsupported file name."""
    source = tmp_path / "example.py"
    source.touch()
    (tmp_path / "example.py\nother.py").touch()
    mocker.patch("pyunslop.discovery.run_ruff", return_value=f"{source}\n")
    with pytest.raises(RuntimeError, match="Newline-containing paths are unsupported"):
        list(find_python_files([tmp_path]))


def test_unicode_separator_is_not_a_record_delimiter(tmp_path: Path) -> None:
    """Split only Ruff's newline delimiter, not valid Unicode filename characters."""
    source = tmp_path / "first\u2028second.py"
    source.touch()
    assert list(find_python_files([tmp_path])) == [source]
