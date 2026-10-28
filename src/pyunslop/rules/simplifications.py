import ast
from . import wrappers, borrowed_client, materialization, named_instances
from ..source import Source
from .constants import single_use_constants
from ..contracts import FunctionNode
from ..diagnostics import Finding
from .comprehensions import check_comprehensions
from ..analysis.bindings import BindingVisitor


class SimplificationAnalyzer(BindingVisitor):
    """Resolve local syntax checks without database or endpoint state."""

    def __init__(self) -> None:
        """Keep findings local to this traversal."""
        super().__init__()
        self.findings: list[Finding] = []

    def visit_Module(self, node: ast.Module) -> None:
        """Review module constants before entering nested scopes."""
        self.findings.extend(single_use_constants(node))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Review function-local constants and exact forwarding boundaries."""
        self.findings.extend(single_use_constants(node))
        self.findings.extend(wrappers.check_function(node, self))
        super().visit_FunctionDef(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Review structural candidates before entering class-local scope."""
        self.findings.extend(wrappers.check_class(node, self))
        self.findings.extend(borrowed_client.check(node))
        super().visit_ClassDef(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Review adjacent list consumers before rebinding names."""
        self.findings.extend(materialization.check_assign(node, self))
        super().visit_Assign(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Review named instances and known iterable-only consumers."""
        self.findings.extend(named_instances.check(node, self))
        self.findings.extend(materialization.check_call(node, self))
        self.generic_visit(node)


def check_simplifications(source: Source) -> list[Finding]:
    """Return conservative syntax-only review candidates."""
    analyzer = SimplificationAnalyzer()
    analyzer.visit(source.tree)
    return [*analyzer.findings, *check_comprehensions(source)]
