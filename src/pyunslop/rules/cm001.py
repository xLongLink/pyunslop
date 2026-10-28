from __future__ import annotations

import ast
import tokenize
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..source import Source
    from ..contracts import CommentFinding

CODE = "CM001"
MAX_CODE_LINES = 10
NON_CODE_TOKENS = {tokenize.COMMENT, tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL}


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


def check(source: Source) -> list[CommentFinding]:
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
                findings.append((line_number, 1, CODE, f"more than {MAX_CODE_LINES} code lines without a standalone comment"))
    return findings
