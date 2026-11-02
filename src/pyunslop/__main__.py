import sys
from pathlib import Path
from pyunslop.ruff import check_ruff
from pyunslop.checker import check_file
from pyunslop.discovery import find_python_files


def main() -> int:
    """Scan the current project with every fixed-preset check enabled."""
    if len(sys.argv) > 1:
        print("pyunslop takes no arguments; run it from your project directory.", file=sys.stderr)
        return 2

    # Collect both rule families before rendering a single sorted report.
    findings = []
    try:
        paths = list(find_python_files([Path()]))
        for path in paths:
            # Native checks share parsing state within each file.
            findings.extend(check_file(path))
        findings.extend(check_ruff())

    except (OSError, RuntimeError) as exc:
        # Execution failures have a different status from lint findings.
        print(f"Could not scan project: {exc}", file=sys.stderr)
        return 2

    # Match Ruff's concise output and exit status for both rule families.
    for finding in sorted(findings, key=lambda item: (str(item.path), item.line, item.column, item.code)):
        print(finding)
    if findings:
        count = len(findings)
        print(f"Found {count} error{'s' if count != 1 else ''}.")
        return 1
    print("All checks passed!")
    return 0


# Module execution uses the same status as the installed console script.
if __name__ == "__main__":
    raise SystemExit(main())
