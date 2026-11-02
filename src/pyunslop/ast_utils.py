import ast
from collections.abc import Iterator


def fixed_arguments(arguments: ast.arguments) -> list[ast.arg]:
    """Return positional and keyword-only parameters in declaration order, excluding variadics."""
    return [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]


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


def adjacent_statement(parent: ast.AST, node: ast.stmt, offset: int) -> ast.stmt | None:
    """Find a neighboring statement without crossing its containing list boundary."""
    for _, statements in ast.iter_fields(parent):
        if isinstance(statements, list) and node in statements:
            index = statements.index(node) + offset

            # Negative offsets must not wrap to the end of a block.
            if 0 <= index < len(statements):
                return statements[index]
    return None


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
