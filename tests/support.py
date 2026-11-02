import re
from subprocess import CompletedProcess
from collections.abc import Callable

RunCLI = Callable[..., CompletedProcess[str]]


def native_codes(result: CompletedProcess[str]) -> list[str]:
    """Read native rule codes without mistaking Ruff or execution failures for acceptance."""
    assert result.stderr == "", result.stderr
    assert result.returncode in (0, 1), result.stdout
    assert "invalid-syntax" not in result.stdout, result.stdout
    assert result.returncode == (0 if result.stdout == "All checks passed!\n" else 1), result.stdout
    return re.findall(r"^.+:\d+:\d+: (SLOP\d{3}) ", result.stdout, re.MULTILINE)
