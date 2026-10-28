from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..source import Source
    from ..contracts import CommentFinding

CODE = "CM001"
MAX_CODE_LINES = 10


def check(source: Source) -> list[CommentFinding]:
    """Report the first line over the fixed limit in each uncommented run."""
    findings = []
    since_comment = 0
    for line_number in range(1, len(source.lines) + 1):
        if line_number in source.function_starts:
            since_comment = 0
        if line_number in source.standalone_comments:
            since_comment = 0

        # Blank lines and inline comments do not reset an uncommented run.
        elif line_number in source.code_lines:
            since_comment += 1
            if since_comment == MAX_CODE_LINES + 1:
                findings.append((line_number, 1, CODE, f"more than {MAX_CODE_LINES} code lines without a standalone comment"))
    return findings
