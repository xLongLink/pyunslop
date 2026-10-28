from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..source import Source
    from ..contracts import CommentFinding

CODE = "CM002"


def check(source: Source) -> list[CommentFinding]:
    """Require separation before comment blocks outside suites and continuations."""
    findings = []
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
            and line_number not in source.continued_comments
            and not starts_suite
        ):
            findings.append((line_number, 1, CODE, "expected a blank line before the comment block"))
    return findings
