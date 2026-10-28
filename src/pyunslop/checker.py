import ast
import io
import os
import tokenize
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .query_rules import check_queries

MAX_CODE_LINES = 10

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

# Layout tokens must not inflate the physical code-line count.
NON_CODE_TOKENS = {
    tokenize.COMMENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.NEWLINE,
    tokenize.NL,
}


# Structured findings can be consumed without parsing CLI output.
@dataclass(frozen=True)
class Warning:
    """A source location and an actionable warning."""

    path: Path
    line: int
    column: int
    code: str
    message: str

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column}: "
            f"warning: {self.code} {self.message}"
        )


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
                directories[:] = sorted(
                    directory
                    for directory in directories
                    if directory not in EXCLUDED_DIRS
                )

                # Sorting both directory and file names keeps diagnostics reproducible.
                candidates.extend(
                    Path(root) / filename
                    for filename in sorted(filenames)
                    if filename.endswith(".py")
                )
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
        lines = source.splitlines()

        # The AST identifies imports and literals that token counting would overcount.
        import_lines: set[int] = set()
        function_starts: set[int] = set()
        string_continuations: set[int] = set()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_starts.add(node.lineno)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # Imports are excluded even when they span several physical lines.
                import_lines.update(
                    range(node.lineno, (node.end_lineno or node.lineno) + 1)
                )

            # Adjacent literals share one AST node, even across source lines.
            elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
                string_continuations.update(
                    range(node.lineno + 1, (node.end_lineno or node.lineno) + 1)
                )

        # Tokenization distinguishes real comments from hashes inside strings.
        standalone_comments: set[int] = set()
        continued_comments: set[int] = set()
        code_lines: set[int] = set()
        warnings: list[Warning] = []
        bracket_depth = 0

        # Placement depends on bracket depth at the comment, not on indentation alone.
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            line_number, column = token.start
            if token.type == tokenize.COMMENT:
                if not token.line[:column].strip():
                    standalone_comments.add(line_number)
                    if bracket_depth:
                        continued_comments.add(line_number)

                # A shebang is special only on the first source line.
                is_shebang = line_number == 1 and token.string.startswith("#!")
                if (
                    not is_shebang
                    and token.string != "#"
                    and not token.string.startswith("# ")
                ):
                    # Columns are one-based in diagnostics, unlike tokenize offsets.
                    warnings.append(
                        Warning(
                            path, line_number, column + 1, "CM003",
                            "expected a space after '#'",
                        )
                    )

            # Count each physical line once, even if it contains several tokens.
            elif token.type not in NON_CODE_TOKENS:
                string_continuation = (
                    token.type == tokenize.STRING
                    and line_number in string_continuations
                )
                if line_number not in import_lines and not string_continuation:
                    code_lines.add(line_number)

                # Comments within open delimiters are exempt from CM002.
                if token.type == tokenize.OP:
                    if token.string in ("(", "[", "{"):
                        bracket_depth += 1
                    elif token.string in (")", "]", "}"):
                        bracket_depth -= 1
    except (OSError, SyntaxError, UnicodeError, tokenize.TokenError):
        return []

    # Only standalone comments and function boundaries reset frequency.
    since_comment = 0
    for line_number, line in enumerate(lines, start=1):
        if line_number in function_starts:
            since_comment = 0
        if line_number in standalone_comments:
            previous = lines[line_number - 2] if line_number > 1 else ""
            starts_suite = previous.rstrip().endswith(":") and (
                len(line.expandtabs()) - len(line.expandtabs().lstrip())
                > len(previous.expandtabs()) - len(previous.expandtabs().lstrip())
            )

            # Consecutive comments belong to the same block.
            if (
                line_number > 1
                and previous.strip()
                and line_number - 1 not in standalone_comments
                and line_number not in continued_comments
                and not starts_suite
            ):
                # Report the block start rather than every comment in the block.
                warnings.append(
                    Warning(
                        path, line_number, 1, "CM002",
                        "expected a blank line before the comment block",
                    )
                )
            since_comment = 0

        # Emit once per uninterrupted run, at the first line over the limit.
        elif line_number in code_lines:
            since_comment += 1
            if since_comment == MAX_CODE_LINES + 1:
                warnings.append(
                    Warning(
                        path, line_number, 1, "CM001",
                        f"more than {MAX_CODE_LINES} code lines without a standalone comment",
                    )
                )

    # AST rules share the parsed tree and the same warning-only output format.
    warnings.extend(
        Warning(path, node.lineno, node.col_offset + 1, code, message)
        for node, code, message in check_queries(tree)
    )
    return sorted(warnings, key=lambda warning: (warning.line, warning.column, warning.code))
