import sys
from pathlib import Path
from .checker import check_file, find_python_files
from .ruff_checks import check_ruff


def main() -> int:
    """Scan the current project with every fixed-preset check enabled."""
    if len(sys.argv) > 1:
        print("pyunslop takes no arguments; run it from your project directory.", file=sys.stderr)
        return 2

    # Findings are printed rather than raised.
    count = 0
    try:
        paths = list(find_python_files([Path()]))
        for path in paths:
            for warning in check_file(path):
                print(warning)
                count += 1

        # Ruff receives the same files, rather than discovering a different project set.
        for warning in check_ruff(paths):
            print(warning)
            count += 1
    except (OSError, RuntimeError) as exc:
        print(f"Could not scan project: {exc}", file=sys.stderr)
        return 2

    # A warning summary never changes the successful exit status.
    if count:
        print(f"Found {count} warning(s).", file=sys.stderr)
    else:
        print("Checks passed.")
    return 0
