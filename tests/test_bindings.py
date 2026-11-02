import ast
from pyunslop.contracts import FunctionNode
from pyunslop.analysis.bindings import BindingVisitor


class FunctionProbe(BindingVisitor):
    """Record function ownership while traversing definition-time and body expressions."""

    def __init__(self) -> None:
        """Keep observed calls separate from binding state."""
        super().__init__()
        self.calls: list[tuple[str, str | None]] = []

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Visit decorators and defaults before entering the function body."""
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit(node.args)
        super().visit_FunctionDef(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        """Capture the owner seen by an expression analyzer."""
        function = self.current_function
        self.calls.append((ast.unparse(node.func), function.name if function is not None else None))
        self.generic_visit(node)


def test_current_function_tracks_bodies_not_definition_expressions() -> None:
    """Keep nested decorators and defaults in their enclosing scope and restore it afterward."""
    tree = ast.parse(
        "@decorate_outer()\ndef outer(value=default_outer()):\n    before_inner()\n    @decorate_inner()\n    async def inner(value=default_inner()):\n        in_inner()\n    after_inner()\nafter_outer()\n"
    )
    probe = FunctionProbe()

    # Act
    probe.visit(tree)

    # Assert
    assert probe.calls == [
        ("decorate_outer", None),
        ("default_outer", None),
        ("before_inner", "outer"),
        ("decorate_inner", "outer"),
        ("default_inner", "outer"),
        ("in_inner", "inner"),
        ("after_inner", "outer"),
        ("after_outer", None),
    ]
    assert probe.current_function is None
