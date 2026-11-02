import ast
import pytest
from pyunslop.ast_utils import adjacent_statement


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("a()\nb()\n", id="module"),
        pytest.param("if ready:\n    a()\n    b()\nelse:\n    c()\n", id="if-else"),
        pytest.param("for item in items:\n    a()\n    b()\nelse:\n    c()\n", id="loop-else"),
        pytest.param("try:\n    a()\n    b()\nexcept Error:\n    c()\nfinally:\n    d()\n", id="try-finally"),
        pytest.param("try:\n    c()\nexcept Error:\n    a()\n    b()\n", id="except-handler"),
    ],
)
def test_statement_adjacency_stays_inside_its_block(source: str) -> None:
    """Find immediate neighbors without wrapping or crossing compound-statement blocks."""
    tree = ast.parse(source)
    parent = next(node for node in ast.walk(tree) if len(getattr(node, "body", [])) == 2)
    first, second = parent.body

    # Act / Assert
    assert adjacent_statement(parent, first, -1) is None
    assert adjacent_statement(parent, first, 1) is second
    assert adjacent_statement(parent, second, -1) is first
    assert adjacent_statement(parent, second, 1) is None


def test_statement_not_in_parent_has_no_neighbor() -> None:
    """Do not infer adjacency for a statement owned by a different syntax tree."""
    parent = ast.parse("a()\nb()\n")
    unrelated = ast.parse("a()\n").body[0]

    # Act / Assert
    assert adjacent_statement(parent, unrelated, 1) is None
