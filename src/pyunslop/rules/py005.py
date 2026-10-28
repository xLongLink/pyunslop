from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from ..queries import EXPRESSION_FUNCTIONS

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY005"


def in_expression_context(context: AnalysisVisitor) -> bool:
    """Recognize SQL expression parents without crossing unrelated consumers."""
    for parent in reversed(context.parents[:-1]):
        if isinstance(parent, ast.Call):
            if context.qualified(parent.func) in EXPRESSION_FUNCTIONS:
                return True

            # Stop at the first enclosing call, even when it is not a SQL API.
            return (
                isinstance(parent.func, ast.Attribute)
                and parent.func.attr in {"where", "filter", "having"}
                and context.kind(parent.func.value) in {"@statement", "@single_statement"}
            )
    return False


def check(node: ast.Call, context: AnalysisVisitor) -> None:
    """Prefer generators for single-use list comprehensions in SQL in_ calls."""
    if not (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "in_"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.ListComp)
        and not node.keywords
    ):
        return

    # Unrelated objects may also define in_; require expression provenance.
    if context.kind(node.func.value) == "@expression" or in_expression_context(context):
        context.findings.append((node.args[0], CODE, "pass a generator expression directly to SQLAlchemy in_()"))
