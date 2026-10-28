from pathlib import Path
from .checker import Warning as CheckWarning
from .ruff_runner import run_ruff
from .rules.rfmt001 import check as check_format
from collections.abc import Iterable
from importlib.resources import files, as_file


def check_ruff(paths: Iterable[Path]) -> list[CheckWarning]:
    """Return fixed-preset Ruff lint and formatting warnings without modifying files."""
    paths = list(paths)
    warnings: list[CheckWarning] = []
    if not paths:
        return warnings

    # Batching keeps explicit file arguments below platform command-line limits.
    with as_file(files("pyunslop").joinpath("ruff.toml")) as config:
        for offset in range(0, len(paths), 64):
            batch = paths[offset : offset + 64]
            warnings.extend(run_ruff("check", config, batch))
            warnings.extend(check_format(config, batch))
    return warnings
