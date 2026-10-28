from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..source import Source
    from ..contracts import CommentFinding

CODE = "CM003"


def check(source: Source) -> list[CommentFinding]:
    """Require a space after comment markers except bare markers and shebangs."""
    findings = []
    for token in source.comments:
        line, column = token.start
        is_shebang = line == 1 and token.string.startswith("#!")
        if not is_shebang and token.string != "#" and not token.string.startswith("# "):
            findings.append((line, column + 1, CODE, "expected a space after '#'"))
    return findings
