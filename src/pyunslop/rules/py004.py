from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from ..queries import BUFFERED_RESULTS

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import LoopNode

CODE = "PY004"


def check(node: LoopNode, context: AnalysisVisitor) -> None:
    """Avoid materializing buffered results solely for a synchronous loop."""
    iterable = node.iter
    if (
        type(node) is ast.For
        and isinstance(iterable, ast.Call)
        and not iterable.args
        and not iterable.keywords
        and isinstance(iterable.func, ast.Attribute)
        and iterable.func.attr == "all"
        # Unknown or streaming result types must retain their materialization semantics.
        and context.kind(iterable.func.value) in BUFFERED_RESULTS
    ):
        context.findings.append((iterable, CODE, "iterate the buffered query result directly instead of calling all()"))
