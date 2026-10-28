import sys
import subprocess
from pathlib import Path


def test_module_defaults_to_current_directory_and_ignores_werror(tmp_path: Path, source_file: Path) -> None:
    """Support module execution without emitting promotable Python warnings."""
    source_file.write_text("#bad\n")
    result = subprocess.run([sys.executable, "-W", "error", "-m", "pyunslop"], cwd=tmp_path, capture_output=True, text=True, check=False)

    # Assert: subprocess success must still include the expected advisory finding.
    assert result.returncode == 0, result.stderr
    assert "warning: SLOP003" in result.stdout
