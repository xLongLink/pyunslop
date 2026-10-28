from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import LoopNode

CODE = "PY108"


def check_call(node: ast.Call, context: AnalysisVisitor) -> None:
    """Prefer scalar query APIs while retaining existing cardinality consumers."""
    if isinstance(node.func, ast.Attribute) and node.func.attr == "scalars" and context.kind(node.func.value) in context.EXECUTE_RESULTS:
        context.findings.append(
            (node, CODE, "use session.scalars() instead of execute().scalars(); preserve one()/one_or_none() cardinality checks")
        )


def check_assign(node: ast.Assign, context: AnalysisVisitor) -> None:
    """Review single-element row unpacking from known single-selection queries."""
    value = node.value
    single_row = (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr in {"one", "one_or_none", "first"}
        and context.kind(value.func.value) == "@single_execute_result"
    )

    # One-element unpacking is eligible; multi-column row contracts stay intact.
    for target in node.targets:
        if isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == 1 and single_row:
            context.findings.append(
                (target, CODE, "use session.scalars() for single-column row unpacking; preserve the existing cardinality check")
            )


def check_for(node: LoopNode, context: AnalysisVisitor) -> None:
    """Review one-column loop unpacking without changing multi-column queries."""
    if (
        isinstance(node.target, (ast.Tuple, ast.List))
        and len(node.target.elts) == 1
        and context.kind(node.iter) == "@single_execute_result"
    ):
        context.findings.append((node.target, CODE, "use session.scalars() for this single-column query; preserve cardinality checks"))
