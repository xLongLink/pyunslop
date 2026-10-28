from __future__ import annotations

import re
import ast
import tokenize
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding

if TYPE_CHECKING:
    from pyunslop.source import Source
MAX_COMPLEXITY = 10
NON_CODE_TOKENS = {tokenize.COMMENT, tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL}
NOQA_DIRECTIVE = re.compile(r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b", re.IGNORECASE)
CONTROL_HEADERS = {"If", "For", "AsyncFor", "While", "Try", "TryStar", "ExceptHandler", "With", "AsyncWith", "Match", "match_case"}


def is_literal_container(node: ast.AST) -> bool:
    """Recognize data containers without calls, unpacking, or computations."""
    if isinstance(node, ast.Dict):
        return all(key is not None and is_literal_value(key) for key in node.keys) and all(is_literal_value(value) for value in node.values)
    return isinstance(node, (ast.List, ast.Tuple, ast.Set)) and all(is_literal_value(item) for item in node.elts)


def is_literal_value(node: ast.AST) -> bool:
    """Include signed numbers and nested literal containers."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float, complex)
    return is_literal_container(node)


def counted_lines(source: Source) -> tuple[set[int], set[int]]:
    """Collapse literal data, exclude imports, and locate function resets."""
    function_starts: set[int] = set()
    import_lines: set[int] = set()
    string_continuations: set[int] = set()
    literal_spans = []

    # Collect source exclusions separately from token-level counting.
    for node in ast.walk(source.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_starts.add(node.lineno)

        # Imports do not contribute to the complexity budget.
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

        # Adjacent literals share one AST node across their physical source lines.
        elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            string_continuations.update(range(node.lineno + 1, (node.end_lineno or node.lineno) + 1))

        # Keep the opening token, but exclude the rest of each literal's span.
        elif is_literal_container(node):
            literal_spans.append(((node.lineno, node.col_offset), (node.end_lineno, node.end_col_offset)))

    # AST columns are UTF-8 byte offsets; tokenize columns count characters.
    def inside_literal(token: tokenize.TokenInfo) -> bool:
        line, column = token.start
        position = (line, len(source.lines[line - 1][:column].encode("utf-8")))
        return any(start < position < end for start, end in literal_spans)

    # Executable suffixes on a literal's closing line must still count.
    code_lines = {
        token.start[0]
        for token in source.tokens
        if token.type not in NON_CODE_TOKENS
        and token.start[0] not in import_lines
        and not (token.type == tokenize.STRING and token.start[0] in string_continuations)
        and not inside_literal(token)
    }
    return function_starts, code_lines


def control_weights(node: ast.AST, depth: int = 0) -> dict[int, int]:
    """Weight control-flow headers, resetting nesting at function boundaries."""
    weights: dict[int, int] = {}
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        depth = 0

    # Case nodes carry their source location on the pattern.
    elif type(node).__name__ in CONTROL_HEADERS:
        line = node.pattern.lineno if isinstance(node, ast.match_case) else node.lineno
        weights[line] = 2 + depth
        depth += 1

    # Multiple headers on one physical line retain the largest weight.
    for child in ast.iter_child_nodes(node):
        for line, weight in control_weights(child, depth).items():
            weights[line] = max(weights.get(line, 0), weight)
    return weights


def check_frequency(source: Source) -> list[Finding]:
    """Report the first line exceeding the fixed uncommented complexity budget."""
    findings = []
    since_comment = 0
    function_starts, code_lines = counted_lines(source)
    weights = control_weights(source.tree)

    # A reset clears accumulated points, not the structural nesting weights.
    for line_number in range(1, len(source.lines) + 1):
        if line_number in function_starts:
            since_comment = 0
        if line_number in source.standalone_comments:
            since_comment = 0

        # Blank lines and inline comments do not reset an uncommented run.
        elif line_number in code_lines:
            previous = since_comment
            since_comment += weights.get(line_number, 1)

            # Headers can jump past the limit; report only the first crossing.
            if previous <= MAX_COMPLEXITY < since_comment:
                findings.append(
                    Finding(line_number, 1, "SLOP001", f"complexity budget exceeds {MAX_COMPLEXITY} points without a standalone comment")
                )
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
            depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(token.string, 0)
    return comments


def check_separation(source: Source) -> list[Finding]:
    """Require separation before comment blocks outside continuations."""
    findings = []
    continued = continued_comments(source)
    for line_number in sorted(source.standalone_comments):
        previous = source.lines[line_number - 2] if line_number > 1 else ""

        # Only the first comment in an ordinary block needs a preceding blank line.
        if line_number > 1 and previous.strip() and line_number - 1 not in source.standalone_comments and line_number not in continued:

            # Report only the block's opening comment.
            findings.append(Finding(line_number, 1, "SLOP002", "expected a blank line before the comment block"))
    return findings


def check_suppressions(source: Source) -> list[Finding]:
    """Reject suppression directives in real comments, never in string contents."""
    findings = []
    for token in source.comments:
        match = NOQA_DIRECTIVE.search(token.string)
        if match:

            # Match offsets are relative to the token, not the physical source line.
            line, column = token.start
            findings.append(Finding(line, column + match.start() + 1, "SLOP003", "noqa suppression directives are forbidden"))
    return findings


def check_comments(source: Source) -> list[Finding]:
    """Check lexical policies using the file's shared tokens."""
    return [*check_frequency(source), *check_separation(source), *check_suppressions(source)]
