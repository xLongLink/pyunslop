from __future__ import annotations

import tokenize
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..source import Source
    from ..contracts import CommentFinding

CODE = "CM002"


def continued_comments(source: Source) -> set[int]:
    """Locate comments inside bracketed expressions, where separation is optional."""
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


def check(source: Source) -> list[CommentFinding]:
    """Require separation before comment blocks outside suites and continuations."""
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
            findings.append((line_number, 1, CODE, "expected a blank line before the comment block"))
    return findings
