from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass

if TYPE_CHECKING:
    from .contracts import LocatedNode


@dataclass(frozen=True)
class Finding:
    """A native diagnostic independent of AST or token representation."""

    line: int
    column: int
    code: str
    message: str

    @classmethod
    def at(cls, node: LocatedNode, code: str, message: str) -> Finding:
        """Capture a one-based location without retaining the syntax tree."""
        return cls(node.lineno, node.col_offset + 1, code, message)


# Public warnings add file identity; native findings do not retain paths or trees.
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
