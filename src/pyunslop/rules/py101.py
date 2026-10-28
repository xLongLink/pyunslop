from __future__ import annotations

import ast
from .py010 import is_external
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY101"


def check(node: ast.Return, context: AnalysisVisitor) -> None:
    """Review duplicate response validation while preserving visible transformations."""
    if not context.functions:
        return
    function = context.functions[-1]
    routes = context.routes[id(function)]
    if not routes or any(is_external(route) for route in routes):
        return

    # Only a direct model_validate return can duplicate this route contract.
    value = node.value
    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "model_validate"):
        return

    # Explicit options and computed inputs may intentionally transform the result.
    if len(value.args) != 1 or value.keywords or not isinstance(value.args[0], (ast.Name, ast.Attribute)):
        return
    model = context.qualified(value.func.value)
    if model and model not in context.transforming_models and context.response_models[id(function)] == {model}:
        context.findings.append(
            (value, CODE, "route already validates this response model; avoid reconstruction unless validation intentionally transforms it")
        )
