import json
import subprocess  # noqa: S404
from pathlib import Path
from .checker import Warning as CheckWarning
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, distribution
from importlib.resources import files, as_file


def check_ruff(paths: Iterable[Path]) -> list[CheckWarning]:
    """Return fixed-preset Ruff lint and formatting warnings without modifying files."""
    paths = list(paths)
    warnings = []
    if not paths:
        return warnings

    # Batching keeps explicit file arguments below platform command-line limits.
    with as_file(files("pyunslop").joinpath("ruff.toml")) as config:
        for offset in range(0, len(paths), 64):
            batch = paths[offset : offset + 64]
            warnings.extend(run_ruff("check", config, batch))
            warnings.extend(run_ruff("format", config, batch))
    return warnings


def ruff_binary() -> Path:
    """Locate the installed binary without importing a project's ruff.py module."""
    try:
        installed = distribution("ruff")
    except PackageNotFoundError as exc:
        raise RuntimeError("Ruff is not installed") from exc
    for entry in installed.files or []:
        if entry.name in {"ruff", "ruff.exe"}:
            return Path(installed.locate_file(entry)).resolve()
    raise RuntimeError("The installed Ruff distribution has no executable")


def run_ruff(command: str, config: Path, paths: list[Path]) -> list[CheckWarning]:
    """Convert Ruff's JSON diagnostics to the shared warning representation."""
    args = [str(ruff_binary()), command, "--config", str(config), "--no-cache", "--output-format", "json"]

    # Resolve the tests pattern at the scanned project root, not the installed preset directory.
    args += ["--config", 'lint.per-file-ignores = {"tests/**" = ["ARG", "N803", "S"]}']
    args += ["--no-fix"] if command == "check" else ["--check"]
    result = subprocess.run(args + ["--", *map(str, paths)], capture_output=True, text=True, check=False)  # noqa: S603
    try:
        diagnostics = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff {command} failed: {result.stderr.strip() or result.stdout.strip()}") from exc

    # A formatter parse diagnostic is a finding, even when Ruff exits with status 2.
    if not isinstance(diagnostics, list) or (result.returncode not in {0, 1} and not diagnostics):
        raise RuntimeError(f"Ruff {command} failed: {result.stderr.strip()}")

    # Preserve Ruff's source locations and codes, with one stable formatter warning code.
    return [
        CheckWarning(
            Path(item["filename"]),
            item["location"]["row"],
            item["location"]["column"],
            "RFMT001" if item["code"] == "unformatted" else item["code"],
            item["message"],
        )
        for item in diagnostics
    ]
