from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import QualifiedName

CODE = "PY010"


def is_external(route: ast.Call) -> bool:
    """Recognize explicit external-protocol contracts shared with response reviews."""
    values = {keyword.arg: keyword.value for keyword in route.keywords}
    extra = values.get("openapi_extra")
    if isinstance(extra, ast.Dict):
        return any(
            isinstance(key, ast.Constant) and key.value == "x-external-protocol" and isinstance(value, ast.Constant) and value.value is True
            for key, value in zip(extra.keys, extra.values)
        )
    return False


def is_success_envelope(node: ast.AST | None, qualified: QualifiedName) -> bool:
    """Identify literal success envelopes without guessing dynamic payload shapes."""
    if isinstance(node, ast.Dict):
        fields: dict[str | None, ast.expr] = {
            key.value: value for key, value in zip(node.keys, node.values) if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    elif isinstance(node, ast.Call) and qualified(node.func) == "dict" and not node.args:
        fields = {keyword.arg: keyword.value for keyword in node.keywords}
    else:
        return False

    # A success flag alone is not an envelope unless it wraps detail or data.
    success = fields.get("success")
    return isinstance(success, ast.Constant) and success.value is True and bool({"detail", "data"} & fields.keys())


def kind(node: ast.AST, context: AnalysisVisitor) -> str:
    """Propagate known envelopes through the shared local binding tracker."""
    return "@envelope" if is_success_envelope(node, context.qualified) else ""


def check(node: ast.Return, context: AnalysisVisitor) -> None:
    """Review API envelopes while preserving explicit external protocols."""
    if not context.functions:
        return
    routes = context.routes[id(context.functions[-1])]
    if routes and not any(is_external(route) for route in routes) and node.value is not None and context.kind(node.value) == "@envelope":
        context.findings.append((node.value, CODE, "return the API payload directly instead of a generic success envelope"))
