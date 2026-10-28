from pathlib import Path
from ..checker import Warning as CheckWarning
from dataclasses import replace
from ..ruff_runner import run_ruff

CODE = "RFMT001"


def check(config: Path, paths: list[Path]) -> list[CheckWarning]:
    """Report read-only Ruff format findings while preserving parse diagnostic codes."""
    return [replace(warning, code=CODE) if warning.code == "unformatted" else warning for warning in run_ruff("format", config, paths)]
