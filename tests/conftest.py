import os
import sys
import pytest
import textwrap
import subprocess
from pathlib import Path
from tests.support import RunCLI


@pytest.fixture
def run_cli(tmp_path: Path) -> RunCLI:
    """Run the local module and real Ruff checks in an isolated project."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    def run(source: str | dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
        sources = {"example.py": source} if isinstance(source, str) else source
        contents = {name: textwrap.dedent(text).lstrip("\n") for name, text in sources.items()}
        for name, text in contents.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        # Act
        result = subprocess.run(
            [sys.executable, "-m", "pyunslop", *arguments], cwd=tmp_path, env=env, capture_output=True, text=True, check=False, timeout=30
        )

        # Assert
        for name, text in contents.items():
            assert (tmp_path / name).read_text(encoding="utf-8") == text
        return result

    return run
