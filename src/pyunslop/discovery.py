import os
from pathlib import Path
from collections.abc import Iterable, Iterator

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


def find_python_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Yield Python files once, skipping generated directories during traversal.

    Explicit file paths are checked even inside excluded directories.
    Missing paths raise OSError rather than silently skipping a typo.
    """
    seen: set[Path] = set()

    def walk_error(error: OSError) -> None:
        raise error

    for path in paths:
        # Explicit files bypass directory exclusions, but still require a Python suffix.
        if path.is_file():
            candidates = [path] if path.suffix == ".py" else []

        # Directory scans prune generated trees before collecting Python files.
        elif path.is_dir():
            candidates = []
            for root, directories, filenames in os.walk(path, onerror=walk_error):
                # Prune in place so os.walk never enters excluded directories.
                directories[:] = sorted(directory for directory in directories if directory not in EXCLUDED_DIRS)
                candidates.extend(Path(root) / filename for filename in sorted(filenames) if filename.endswith(".py"))
        else:
            raise FileNotFoundError(f"{path}: path not found or not a file/directory")

        # Resolve for identity but retain the user's path spelling in diagnostics.
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate
