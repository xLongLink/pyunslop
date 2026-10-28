from __future__ import annotations

import ast
from typing import TYPE_CHECKING, cast
from pyunslop.diagnostics import Finding

if TYPE_CHECKING:
    from pyunslop.contracts import ScopeNode

CODE = "SLOP023"

# Each boundary can capture or shadow a name from an enclosing literal assignment.
SCOPE_BOUNDARIES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


def immutable_literal(node: ast.AST) -> bool:
    """Recognize literals without mutable members or runtime computation."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Tuple):
        return all(immutable_literal(element) for element in node.elts)

    # Signed numeric literals are unary expressions, not Constant nodes.
    if not isinstance(node, ast.UnaryOp) or not isinstance(node.op, (ast.UAdd, ast.USub)):
        return False
    return isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float, complex)


def mentions_binding(node: ast.AST, name: str) -> bool:
    """Include bindings stored as strings rather than Name nodes."""
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.arg):
        return node.arg == name

    # Definitions bind their names without an ast.Name store.
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name

    # Imports, declarations, and captures may bind names without a Name node.
    if isinstance(node, ast.alias):
        return (node.asname or node.name.split(".")[0]) == name
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return name in node.names
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return node.name == name
    return isinstance(node, ast.MatchMapping) and node.rest == name


def constant_target(statement: ast.stmt, private_only: bool) -> ast.Name | None:
    """Keep annotated contracts, public module APIs, and computed values intact."""
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or statement.type_comment:
        return None
    target = statement.targets[0]
    if not isinstance(target, ast.Name) or not target.id.isupper() or not immutable_literal(statement.value):
        return None
    return target if not private_only or target.id.startswith("_") else None


def single_use_constants(scope: ScopeNode) -> list[Finding]:
    """Find conservative, same-scope literal-inlining review candidates."""
    nodes = list(ast.walk(scope))
    if any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"globals", "locals", "vars", "eval", "exec"}
        for node in nodes
    ):
        return []

    # Export lists can publish private names through string references.
    if isinstance(scope, ast.Module) and any(isinstance(node, ast.Name) and node.id == "__all__" for node in nodes):
        return []

    # Nested scopes can capture or shadow an otherwise single use.
    nested: set[ast.AST] = set()
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()

        # A boundary's walk includes deeper scopes; do not expand them separately.
        if isinstance(node, SCOPE_BOUNDARIES):
            nested.update(ast.walk(node))
        else:
            pending.extend(ast.iter_child_nodes(node))

    # Check assignments against both complete references and nested-scope mentions.
    findings: list[Finding] = []
    for statement in scope.body:
        target = constant_target(statement, isinstance(scope, ast.Module))
        if target is None:
            continue

        # Only one store followed by one same-scope load is eligible.
        references = [node for node in nodes if mentions_binding(node, target.id)]
        if len(references) != 2 or any(reference in nested for reference in references):
            continue
        uses = [node for node in references if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)]

        # Moving a literal before its assignment would change execution behavior.
        if len(uses) == 1 and (uses[0].lineno, uses[0].col_offset) > (cast(int, statement.end_lineno), cast(int, statement.end_col_offset)):
            message = f"review inlining single-use constant {target.id}; preserve meaningful names and intentional boundaries"
            findings.append(Finding.at(target, CODE, message))
    return findings
