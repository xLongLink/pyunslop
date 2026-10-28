from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY001"


def check(node: ast.Attribute, context: AnalysisVisitor) -> None:
    """Require a name before consuming an awaited query result."""
    if isinstance(node.value, ast.Await) and context.kind(node.value) in context.RESULT_KINDS:
        context.findings.append((node, CODE, "name the asynchronous query result before consuming it"))
