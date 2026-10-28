import ast
import textwrap
import unittest
from pyunslop.ast_utils import name_loads, scope_nodes


class AstUtilsTests(unittest.TestCase):
    """Check scope boundaries used by conservative syntax reviews."""

    def test_name_loads_include_closures_but_not_stores(self) -> None:
        """A nested read must count as reuse of the enclosing value."""

        # Arrange
        tree = ast.parse("value = 1\ndef later():\n    return value\nother = different\n")

        # Act
        loads = name_loads(tree, "value")

        # Assert
        assert [(node.lineno, type(parent)) for node, parent in loads] == [(3, ast.Return)]

    def test_scope_nodes_exclude_nested_scopes(self) -> None:
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
