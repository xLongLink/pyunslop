from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from ..ast_utils import name_loads, scope_nodes

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import FunctionNode, QualifiedName

CODE = "PY109"


def size_use(node: ast.AST, parent: ast.AST, qualified: QualifiedName) -> bool:
    """Recognize length consumers and direct truth tests."""
    if isinstance(parent, ast.Call):
        return qualified(parent.func) in {"len", "bool"} and parent.args == [node] and not parent.keywords
    if isinstance(parent, (ast.If, ast.While, ast.IfExp)):
        return parent.test is node
    return isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not)


def only_size_uses(function: FunctionNode, name: str, qualified: QualifiedName) -> bool:
    """Preserve row data whenever it is rebound or used beyond size checks."""
    uses = name_loads(function, name)
    stores = [node for node in scope_nodes(function) if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store)]
    return len(stores) == 1 and bool(uses) and all(size_use(node, parent, qualified) for node, parent in uses)


def check(node: ast.Call, context: AnalysisVisitor) -> None:
    """Review existence or bounded queries without rewriting locking semantics."""
    if context.kind(node) != "@rows" or len(context.parents) < 2:
        return
    parent = context.parents[-2]
    candidate = size_use(node, parent, context.qualified)
    if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) and context.functions:
        candidate = only_size_uses(context.functions[-1], parent.targets[0].id, context.qualified)

    # Size-only use does not authorize changing locks or transaction semantics.
    if candidate:
        context.findings.append(
            (node, CODE, "review an existence or bounded query instead of loading rows solely for size/truth; preserve locking")
        )
