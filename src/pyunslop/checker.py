import os
import ast
import tokenize
from .rules import COMMENT_RULES
from .source import Source
from pathlib import Path
from .analysis import check_patterns
from dataclasses import dataclass
from collections.abc import Iterable, Iterator

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    # Build outputs and installed dependencies are not project source.
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


# Structured findings can be consumed without parsing CLI output.
@dataclass(frozen=True)
class Warning:  # noqa: A001
    """A source location and an actionable warning."""

    path: Path
    line: int
    column: int
    code: str
    message: str

    def __str__(self) -> str:
        """Format an editor-friendly, one-based source location and warning."""
        return f"{self.path}:{self.line}:{self.column}: warning: {self.code} {self.message}"


def find_python_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Yield Python files once, skipping generated directories during traversal.

    Explicit file paths are checked even inside excluded directories.
    Missing paths raise OSError rather than silently skipping a typo.
    """
    seen: set[Path] = set()

    def walk_error(error: OSError) -> None:
        raise error

    for path in paths:
        if path.is_file():
            candidates = [path] if path.suffix == ".py" else []
        elif path.is_dir():
            candidates = []
            for root, directories, filenames in os.walk(path, onerror=walk_error):
                # Prune in place so os.walk never enters excluded directories.
                directories[:] = sorted(directory for directory in directories if directory not in EXCLUDED_DIRS)

                # Sorting both directory and file names keeps diagnostics reproducible.
                candidates.extend(Path(root) / filename for filename in sorted(filenames) if filename.endswith(".py"))
        else:
            raise FileNotFoundError(f"{path}: path not found or not a file/directory")

        # Resolve for identity but retain the user's path spelling in diagnostics.
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate


def check_file(path: Path) -> list[Warning]:
    """Return warnings without emitting Python warnings or changing the file.

    Unreadable or invalid source is skipped. All rules are enabled, with a fixed
    ten-line comment limit. Function definitions and standalone comments reset CM001.
    """
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        tree = ast.parse(source)
        facts = Source(source, tree)
    except (OSError, SyntaxError, UnicodeError, tokenize.TokenError):
        return []

    # Every rule owns its findings; parsing and warning presentation stay shared.
    warnings = [Warning(path, line, column, code, message) for check in COMMENT_RULES for line, column, code, message in check(facts)]
    warnings.extend(Warning(path, node.lineno, node.col_offset + 1, code, message) for node, code, message in check_patterns(tree, source))
    return sorted(warnings, key=lambda warning: (warning.line, warning.column, warning.code))
