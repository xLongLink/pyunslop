import pytest
from pathlib import Path
from pyunslop import find_python_files


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
