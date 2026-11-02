import sys
import json
import subprocess
from pathlib import Path
from pyunslop.diagnostics import Diagnostic

TIMEOUT_SECONDS = 120


def run_ruff(command: str, *arguments: str) -> str:
    """Run a bounded Ruff command and distinguish findings from execution failures."""
    config = Path(__file__).with_name("ruff.toml")
    args = [sys.executable, "-m", "ruff", command, "--config", str(config), *arguments]

    # The deadline applies to discovery as well as lint and format checks.
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Ruff timed out after {TIMEOUT_SECONDS} seconds") from exc

    # Ruff's formatter exits two for syntax errors as well as execution failures.
    if result.returncode == 2 and command == "format" and "--check" in arguments and not result.stderr:
        try:
            diagnostics = _decode_diagnostics(result.stdout)

            # Accept status two only after validating every returned diagnostic.
            if any(item.code == "invalid-syntax" for item in diagnostics):
                return result.stdout
        except (ValueError, KeyError, TypeError):
            pass

    # Exit code one denotes ordinary findings; other failures stop the scan.
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Ruff failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def parse_diagnostic(item: object) -> Diagnostic:
    """Validate the Ruff fields used by sorting and rendering."""
    if not isinstance(item, dict):
        raise ValueError("expected a diagnostic object")

    # Ruff's lint syntax errors have a diagnostic name but no rule code.
    if item.get("code") is None and item.get("name") == "invalid-syntax":
        item = {**item, "code": "invalid-syntax"}
    if any(not isinstance(item.get(key), str) or not item[key] for key in ("filename", "code", "message")):
        raise ValueError("expected nonempty diagnostic strings")

    # Coordinates must be positive integers, not booleans or numeric strings.
    location = item.get("location")
    if not isinstance(location, dict) or any(type(location.get(key)) is not int or location[key] < 1 for key in ("row", "column")):
        raise ValueError("expected positive diagnostic coordinates")
    path = Path(item["filename"]).relative_to(Path.cwd())
    return Diagnostic(path, location["row"], location["column"], item["code"], item["message"])


def _decode_diagnostics(output: str) -> list[Diagnostic]:
    """Validate an entire Ruff diagnostic array before accepting any entries."""
    items = json.loads(output)
    if not isinstance(items, list):
        raise ValueError("expected a diagnostic array")
    return [parse_diagnostic(item) for item in items]


def check_ruff() -> list[Diagnostic]:
    """Collect Ruff lint and format diagnostics without modifying files."""
    findings = []
    for command, mode in (("check", "--no-fix"), ("format", "--check")):
        output = run_ruff(command, mode, "--output-format", "json", "--quiet", ".")

        # Invalid structured output must never be treated as a clean result.
        try:
            findings.extend(_decode_diagnostics(output))

        # Keep parser and schema errors on the CLI's operational-error path.
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("Ruff returned invalid diagnostics") from exc
    return list(dict.fromkeys(findings))
