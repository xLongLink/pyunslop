import pytest
from pathlib import Path
from pyunslop import Warning as CheckWarning
from pyunslop import check_file
from collections.abc import Callable


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    """Return a source path within the current test's isolated project."""
    return tmp_path / "example.py"


@pytest.fixture
def check_source(source_file: Path) -> Callable[[str], list[CheckWarning]]:
    """Write an exact source fixture and return its native findings."""

    def check(source: str) -> list[CheckWarning]:
        source_file.write_text(source, encoding="utf-8")
        return check_file(source_file)

    return check
