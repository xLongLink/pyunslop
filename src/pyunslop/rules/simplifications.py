import ast
from pyunslop.rules import wrappers, borrowed_client, materialization, named_instances
from pyunslop.source import Source
from pyunslop.contracts import FunctionNode
from pyunslop.diagnostics import Finding
from pyunslop.rules.constants import single_use_constants
from pyunslop.analysis.bindings import Binding, BindingVisitor
from pyunslop.rules.comprehensions import check_comprehensions


class SimplificationAnalyzer(BindingVisitor):
    """Resolve local syntax checks without database or endpoint state."""

    def __init__(self, source: Source) -> None:
        """Keep findings local to this traversal."""
        super().__init__()
        self.findings: list[Finding] = []
        self.constructors = named_instances.Constructors(source.path)

    def kind(self, node: ast.AST | None) -> str:
        """Propagate proven constructor identities through assignment aliases."""
        if isinstance(node, ast.Attribute):
            return self.constructors.resolve(node, self)
        return super().kind(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Preserve module identity and local constructor-resolution evidence."""
        super().visit_Import(node)
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            module = alias.name if alias.asname else name
            self.bindings[name] = Binding(identity=self.bindings[name].identity, value=self.constructors.module(module))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Resolve directly exported classes in local source modules."""
        super().visit_ImportFrom(node)
        module = self.constructors.module(node.module or "", node.level)
        for alias in node.names:
            name = alias.asname or alias.name
            self.bindings[name] = Binding(identity=self.bindings[name].identity, value=self.constructors.member(module, alias.name))

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
        if not node.decorator_list:
            self.bindings[node.name] = Binding(identity=node.name, value=self.constructors.register(node))

    def visit_Assign(self, node: ast.Assign) -> None:
        """Review adjacent list consumers before rebinding names."""
        self.findings.extend(materialization.check_assign(node, self))
        super().visit_Assign(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Review named instances and known iterable-only consumers."""
        self.findings.extend(self.constructors.check(node, self))
        self.findings.extend(materialization.check_call(node, self))
        self.generic_visit(node)


def check_simplifications(source: Source) -> list[Finding]:
    """Return conservative syntax-only review candidates."""
    analyzer = SimplificationAnalyzer(
        source,
    )
    analyzer.visit(source.tree)
    return [*analyzer.findings, *check_comprehensions(source)]
