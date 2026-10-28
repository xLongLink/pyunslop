from __future__ import annotations

import ast
from .py003 import is_copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY002"


class Rule:
    """Report each function's return contract at most once."""

    def __init__(self) -> None:
        """Start with no reported contracts for this file."""
        self.reported_returns: set[int] = set()

    def check(self, node: ast.Return, context: AnalysisVisitor) -> None:
        """Recommend a sequence contract for directly returned query rows."""
        if not context.functions:
            return
        function = context.functions[-1]
        contract = context.annotation(function.returns)

        # Point to the contract once, even when several returns have the same issue.
        if (
            contract in {"list", "typing.List"}
            and (context.kind(node.value) == "@rows" or is_copy(node.value, context))
            and id(function) not in self.reported_returns
            and function.returns is not None
        ):
            self.reported_returns.add(id(function))
            context.findings.append((function.returns, CODE, "use Sequence[T] for a read-only query-result return type"))
