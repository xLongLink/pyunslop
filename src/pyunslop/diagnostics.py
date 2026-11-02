from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path
from dataclasses import field, dataclass

if TYPE_CHECKING:
    from pyunslop.contracts import LocatedNode


@dataclass(frozen=True)
class Finding:
    """A native diagnostic independent of AST or token representation."""

    line: int
    column: int
    code: str
    message: str

    # Coordinate provenance is not part of a finding's identity.
    byte_column: bool = field(default=False, compare=False, repr=False)

    @classmethod
    def at(cls, node: LocatedNode, code: str, message: str) -> Finding:
        """Capture a one-based UTF-8 byte location without retaining the syntax tree."""
        return cls(node.lineno, node.col_offset + 1, code, message, byte_column=True)


# Public diagnostics add file identity; native findings do not retain paths or trees.
@dataclass(frozen=True)
class Diagnostic:
    """A source location and an actionable diagnostic."""

    path: Path
    line: int
    column: int
    code: str
    message: str

    def __str__(self) -> str:
        """Format a Ruff-style, one-based source location and diagnostic."""
        return f"{self.path}:{self.line}:{self.column}: {self.code} {self.message}"


Warning = Diagnostic
