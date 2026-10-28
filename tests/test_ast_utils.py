import ast
import pytest
import textwrap
from pyunslop.ast_utils import name_loads, scope_nodes, immutable_literal, statement_positions


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("None", True),
        ("True", True),
        ("-3", True),
        ("+2.5", True),
        ("-2j", True),
        ("(1, (-2j, None))", True),
        ("-True", False),
        ("--1", False),
        ("(1, [])", False),
        ("[1]", False),
        ("1 + 2", False),
        ("(*values,)", False),
    ],
)
def test_immutable_literal_preserves_syntax_boundaries(expression: str, expected: bool) -> None:
    """Distinguish immutable literals from mutable members and computation."""
    assert immutable_literal(ast.parse(expression, mode="eval").body) is expected


@pytest.mark.parametrize(
    "block",
    [
        "if ready:\n{body}",
        "if ready:\n    pass\nelse:\n{body}",
        "try:\n    pass\nexcept Error:\n{body}",
        "try:\n    pass\nfinally:\n{body}",
    ],
)
def test_statement_positions_cover_statement_lists(block: str) -> None:
    """Locate first, middle, and last statements across compound blocks."""
    tree = ast.parse(block.format(body="    first()\n    middle()\n    last()"))
    statements = [node for node in ast.walk(tree) if isinstance(node, ast.Expr)]
    parent = tree.body[0]
    if isinstance(parent, ast.Try) and parent.handlers:
        parent = parent.handlers[0]

    # Assert
    for index, node in enumerate(statements):
        assert list(statement_positions(parent, node)) == [(statements, index)]


def test_statement_positions_ignore_nodes_outside_list_fields() -> None:
    """Neither an absent statement nor a scalar AST field is a sibling list."""
    node = ast.Pass()
    parent = ast.AST()
    parent._fields = ("scalar", "body")
    parent.scalar = node
    parent.body = [ast.Pass()]
    assert list(statement_positions(parent, node)) == []


def test_name_loads_include_closures_but_not_stores() -> None:
    """A nested read must count as reuse of the enclosing value."""

    # Arrange
    tree = ast.parse("value = 1\ndef later():\n    return value\nother = different\n")

    # Act
    loads = name_loads(tree, "value")

    # Assert
    assert [(node.lineno, type(parent)) for node, parent in loads] == [(3, ast.Return)]


def test_scope_nodes_exclude_nested_scopes() -> None:
    """Nested functions, classes, and lambdas must not affect local analysis."""

    # Arrange
    tree = ast.parse(
        textwrap.dedent("""\
        def outer():
            local = visible
            def inner():
                return hidden
            async def async_inner():
                return also_hidden
            class Nested:
                value = hidden_class
            callback = lambda: hidden_lambda
            return local
        """)
    )

    # Act
    nodes = list(scope_nodes(tree.body[0]))

    # Assert
    assert {node.id for node in nodes if isinstance(node, ast.Name)} == {"local", "visible", "callback"}
