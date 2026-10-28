from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding

if TYPE_CHECKING:
    from pyunslop.contracts import FunctionNode, QualifiedName
    from pyunslop.analysis.bindings import BindingVisitor

CODE = "SLOP020"


def forwarded_function(node: FunctionNode) -> bool:
    """Recognize private exact forwarding without explicit public contracts."""
    if not node.name.startswith("_") or node.name.endswith("__") or node.decorator_list or node.returns:
        return False
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.defaults or node.args.kw_defaults or any(arg.annotation for arg in args):
        return False

    # Extra statements or documentation can establish an intentional boundary.
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
        return False

    # Async wrappers may forward the awaited result just like synchronous wrappers.
    call = node.body[0].value
    if isinstance(call, ast.Await):
        call = call.value
    if not isinstance(call, ast.Call) or call.keywords or node.args.vararg or node.args.kwarg:
        return False
    if isinstance(call.func, ast.Name) and call.func.id == node.name:
        return False

    # Reordering or transforming arguments adds behavior beyond forwarding.
    return len(call.args) == len(args) and all(isinstance(value, ast.Name) and value.id == arg.arg for value, arg in zip(call.args, args))


def empty_subclass(node: ast.ClassDef, qualified: QualifiedName) -> bool:
    """Keep documented, decorated, and framework-specific subclass boundaries."""
    if node.decorator_list or node.keywords or len(node.bases) != 1 or ast.get_docstring(node):
        return False
    if not (node.name.startswith("_") or qualified(node.bases[0]) in {"fastapi.testclient.TestClient", "starlette.testclient.TestClient"}):
        return False

    # Any actual class statement is behavior rather than an empty alias.
    return all(
        isinstance(statement, ast.Pass)
        or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis)
        for statement in node.body
    )


def check_function(node: FunctionNode, context: BindingVisitor) -> list[Finding]:
    """Review exact private wrappers while preserving inherited framework hooks."""
    parent = context.parents[-2] if len(context.parents) > 1 else None
    framework_method = isinstance(parent, ast.ClassDef) and (parent.bases or parent.decorator_list)
    if not framework_method and forwarded_function(node):
        return [Finding.at(node, CODE, "review this transparent forwarding wrapper; preserve public contracts and meaningful boundaries")]
    return []


def check_class(node: ast.ClassDef, context: BindingVisitor) -> list[Finding]:
    """Review subclasses with no added behavior rather than removing them."""
    if empty_subclass(node, context.qualified):
        return [Finding.at(node, CODE, "review this subclass with no added behavior; preserve framework hooks and public contracts")]
    return []
