from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from ..ast_utils import name_loads

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import ASTFinding, FunctionNode, QualifiedName

CODE = "PY107"
ITERABLE_CONSUMERS = {"sum", "min", "max", "tuple", "set", "frozenset"}


def simple_comprehension(node: ast.AST) -> bool:
    """Avoid async, filtering, and visibly effectful list comprehensions."""
    if not isinstance(node, ast.ListComp):
        return False
    if any(isinstance(child, (ast.Call, ast.Await, ast.Yield, ast.NamedExpr, ast.Lambda)) for child in ast.walk(node)):
        return False
    return all(not generator.is_async and not generator.ifs for generator in node.generators)


def temporary_iterable_pair(
    function: FunctionNode, assignment: ast.stmt, following: ast.stmt, qualified: QualifiedName
) -> list[ASTFinding]:
    """Require a single adjacent consumer so intervening code keeps snapshots."""
    if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
        return []
    target = assignment.targets[0]
    if not isinstance(target, ast.Name) or not simple_comprehension(assignment.value):
        return []

    # Closure reads count as reuse, not just references in this statement block.
    uses = name_loads(function, target.id)
    if len(uses) != 1:
        return []
    node, consumer = uses[0]

    # A larger expression could perform work before reaching the consumer.
    if not isinstance(consumer, ast.Call) or getattr(following, "value", None) is not consumer:
        return []
    if qualified(consumer.func) in ITERABLE_CONSUMERS and consumer.args == [node] and not consumer.keywords:
        return [(assignment.value, CODE, "review a generator for this single-use list; preserve snapshot and exception timing")]
    return []


def check_assign(node: ast.Assign, context: AnalysisVisitor) -> None:
    """Review local temporary lists at the point their consumer is resolved."""
    if not context.functions:
        return
    parent = context.parents[-2]
    for _, statements in ast.iter_fields(parent):
        if not isinstance(statements, list) or node not in statements:
            continue

        # Require an immediately adjacent consumer in the same statement list.
        index = statements.index(node)
        if index + 1 < len(statements):
            context.findings.extend(temporary_iterable_pair(context.functions[-1], node, statements[index + 1], context.qualified))


def check_call(node: ast.Call, context: AnalysisVisitor) -> None:
    """Review direct comprehensions passed to known iterable-only consumers."""
    if (
        context.qualified(node.func) in ITERABLE_CONSUMERS
        and len(node.args) == 1
        and not node.keywords
        and simple_comprehension(node.args[0])
    ):
        # Generator conversion still requires checking snapshot and exception timing.
        context.findings.append(
            (node.args[0], CODE, "review a generator for this iterable-only consumer; preserve snapshot and exception timing")
        )
