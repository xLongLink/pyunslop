import json
import subprocess
from typing import TypedDict, cast
from pathlib import Path
from dataclasses import replace
from .diagnostics import Warning as CheckWarning
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, distribution
from importlib.resources import files, as_file


class RuffLocation(TypedDict):
    """A one-based source position supplied by Ruff's JSON output."""

    row: int
    column: int


class RuffDiagnostic(TypedDict):
    """The diagnostic fields consumed from the pinned Ruff engine."""

    filename: str
    location: RuffLocation
    code: str
    message: str


def ruff_binary() -> Path:
    """Locate the installed binary without importing a project's ruff.py module."""
    try:
        installed = distribution("ruff")
    except PackageNotFoundError as exc:
        raise RuntimeError("Ruff is not installed") from exc
    for entry in installed.files or []:
        if entry.name in {"ruff", "ruff.exe"}:
            return Path(str(installed.locate_file(entry))).resolve()
    raise RuntimeError("The installed Ruff distribution has no executable")


def run_ruff(command: str, config: Path, paths: list[Path]) -> list[CheckWarning]:
    """Convert Ruff's JSON diagnostics to the shared warning representation."""
    args = [str(ruff_binary()), command, "--config", str(config), "--no-cache", "--output-format", "json"]

    # Resolve the tests pattern at the scanned project root, not the installed preset directory.
    args += ["--config", 'lint.per-file-ignores = {"tests/**" = ["ARG", "N803", "S"]}']
    args += ["--no-fix", "--ignore-noqa"] if command == "check" else ["--check"]
    result = subprocess.run(args + ["--", *map(str, paths)], capture_output=True, text=True, check=False)
    try:
        diagnostics: object = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff {command} failed: {result.stderr.strip() or result.stdout.strip()}") from exc

    # A formatter parse diagnostic is a finding, even when Ruff exits with status 2.
    if not isinstance(diagnostics, list) or (result.returncode not in {0, 1} and not diagnostics):
        raise RuntimeError(f"Ruff {command} failed: {result.stderr.strip()}")

    return [
        CheckWarning(Path(item["filename"]), item["location"]["row"], item["location"]["column"], item["code"], item["message"])
        for item in cast(list[RuffDiagnostic], diagnostics)
    ]


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
            warnings.extend(
                replace(warning, code="RFMT001") if warning.code == "unformatted" else warning
                for warning in run_ruff("format", config, batch)
            )
    return warnings
