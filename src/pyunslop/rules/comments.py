from __future__ import annotations

import re
import ast
import tokenize
from typing import TYPE_CHECKING
from ..diagnostics import Finding

if TYPE_CHECKING:
    from ..source import Source
MAX_CODE_LINES = 10
NON_CODE_TOKENS = {tokenize.COMMENT, tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL}
NOQA_DIRECTIVE = re.compile(r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b", re.IGNORECASE)


def counted_lines(source: Source) -> tuple[set[int], set[int]]:
    """Exclude imports and string continuations, and locate function resets."""
    function_starts: set[int] = set()
    import_lines: set[int] = set()
    string_continuations: set[int] = set()
    for node in ast.walk(source.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_starts.add(node.lineno)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

        # Adjacent literals share one AST node across their physical source lines.
        elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            string_continuations.update(range(node.lineno + 1, (node.end_lineno or node.lineno) + 1))

    code_lines = {
        token.start[0]
        for token in source.tokens
        if token.type not in NON_CODE_TOKENS
        and token.start[0] not in import_lines
        and not (token.type == tokenize.STRING and token.start[0] in string_continuations)
    }
    return function_starts, code_lines


def check_frequency(source: Source) -> list[Finding]:
    """Report the first line over the fixed limit in each uncommented run."""
    findings = []
    since_comment = 0
    function_starts, code_lines = counted_lines(source)
    for line_number in range(1, len(source.lines) + 1):
        if line_number in function_starts:
            since_comment = 0
        if line_number in source.standalone_comments:
            since_comment = 0

        # Blank lines and inline comments do not reset an uncommented run.
        elif line_number in code_lines:
            since_comment += 1
            if since_comment == MAX_CODE_LINES + 1:
                findings.append(Finding(line_number, 1, "CM001", f"more than {MAX_CODE_LINES} code lines without a standalone comment"))
    return findings


def continued_comments(source: Source) -> set[int]:
    """Locate comments inside bracketed expressions."""
    depth = 0
    comments: set[int] = set()
    for token in source.tokens:
        if token.type == tokenize.COMMENT and depth:
            comments.add(token.start[0])

        # Brackets embedded in strings or comments never change expression depth.
        elif token.type == tokenize.OP:
            if token.string in ("(", "[", "{"):
                depth += 1
            elif token.string in (")", "]", "}"):
                depth -= 1
    return comments


def check_separation(source: Source) -> list[Finding]:
    """Require separation before blocks outside suites and continuations."""
    findings = []
    continued = continued_comments(source)
    for line_number in sorted(source.standalone_comments):
        line = source.lines[line_number - 1]
        previous = source.lines[line_number - 2] if line_number > 1 else ""
        starts_suite = previous.rstrip().endswith(":") and (
            len(line.expandtabs()) - len(line.expandtabs().lstrip()) > len(previous.expandtabs()) - len(previous.expandtabs().lstrip())
        )

        # Only the first comment in an ordinary block needs a preceding blank line.
        if (
            line_number > 1
            and previous.strip()
            and line_number - 1 not in source.standalone_comments
            and line_number not in continued
            and not starts_suite
        ):
            findings.append(Finding(line_number, 1, "CM002", "expected a blank line before the comment block"))
    return findings


def check_spacing(source: Source) -> list[Finding]:
    """Require spaces after comment markers except bare markers and shebangs."""
    findings = []
    for token in source.comments:
        line, column = token.start
        is_shebang = line == 1 and token.string.startswith("#!")
        if not is_shebang and token.string != "#" and not token.string.startswith("# "):
            findings.append(Finding(line, column + 1, "CM003", "expected a space after '#'"))
    return findings


def check_suppressions(source: Source) -> list[Finding]:
    """Reject suppression directives in real comments, never in string contents."""
    findings = []
    for token in source.comments:
        match = NOQA_DIRECTIVE.search(token.string)
        if match:
            line, column = token.start
            findings.append(Finding(line, column + match.start() + 1, "CM004", "noqa suppression directives are forbidden"))
    return findings


def check_comments(source: Source) -> list[Finding]:
    """Check lexical policies using the file's shared tokens."""
    return [*check_frequency(source), *check_separation(source), *check_spacing(source), *check_suppressions(source)]
