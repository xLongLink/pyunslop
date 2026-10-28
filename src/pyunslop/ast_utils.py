import ast
from collections.abc import Iterator


def name_loads(function: ast.AST, name: str) -> list[tuple[ast.Name, ast.AST]]:
    """Include closure reads when counting references to a local value."""
    return [
        (node, parent)
        for parent in ast.walk(function)
        for node in ast.iter_child_nodes(parent)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name
    ]


def scope_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Walk one scope without descending into nested functions or classes."""
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from scope_nodes(child)
