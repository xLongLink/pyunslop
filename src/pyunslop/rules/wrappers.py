from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from pyunslop.ast_utils import fixed_arguments
from pyunslop.diagnostics import Finding

if TYPE_CHECKING:
    from pyunslop.contracts import FunctionNode
    from pyunslop.analysis.bindings import BindingVisitor

CODE = "SLOP020"


def check_function(node: FunctionNode, context: BindingVisitor) -> list[Finding]:
    """Review exact private wrappers while preserving inherited framework hooks."""
    parent = context.parents[-2] if len(context.parents) > 1 else None
    framework_method = isinstance(parent, ast.ClassDef) and (parent.bases or parent.decorator_list)
    if framework_method:
        return []
    if not node.name.startswith("_") or node.name.endswith("__") or node.decorator_list or node.returns:
        return []

    # Defaults and annotations establish intentional call contracts.
    args = fixed_arguments(node.args)
    if node.args.defaults or node.args.kw_defaults or any(arg.annotation for arg in args):
        return []

    # Extra statements or documentation can establish an intentional boundary.
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
        return []

    # Async wrappers may forward the awaited result just like synchronous wrappers.
    call = node.body[0].value
    if isinstance(call, ast.Await):
        call = call.value
    if not isinstance(call, ast.Call) or call.keywords or node.args.vararg or node.args.kwarg:
        return []
    if isinstance(call.func, ast.Name) and call.func.id == node.name:
        return []

    # Reordering or transforming arguments adds behavior beyond forwarding.
    if len(call.args) != len(args) or not all(isinstance(value, ast.Name) and value.id == arg.arg for value, arg in zip(call.args, args)):
        return []
    return [Finding.at(node, CODE, "review this transparent forwarding wrapper; preserve public contracts and meaningful boundaries")]


def check_class(node: ast.ClassDef, context: BindingVisitor) -> list[Finding]:
    """Review subclasses with no added behavior rather than removing them."""
    if node.decorator_list or node.keywords or len(node.bases) != 1 or ast.get_docstring(node):
        return []

    # Preserve public subclasses unless they are known test-client aliases.
    if not (
        node.name.startswith("_")
        or context.qualified(node.bases[0]) in {"fastapi.testclient.TestClient", "starlette.testclient.TestClient"}
    ):
        return []

    # Any actual class statement is behavior rather than an empty alias.
    if not all(
        isinstance(statement, ast.Pass)
        or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis)
        for statement in node.body
    ):
        return []
    return [Finding.at(node, CODE, "review this subclass with no added behavior; preserve framework hooks and public contracts")]
