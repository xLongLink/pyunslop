import ast
from typing import TypeVar
from dataclasses import dataclass
from pyunslop.contracts import LoopNode, WithNode, FunctionNode

Value = TypeVar("Value")


def merge(left: dict[str, Value], right: dict[str, Value], unknown: Value) -> dict[str, Value]:
    """Retain only bindings common to both possible execution paths."""
    return {name: left[name] if name in left and left[name] == right.get(name) else unknown for name in left.keys() | right.keys()}


@dataclass(frozen=True)
class Binding:
    """Keep a name's identity separate from domain-specific value provenance."""

    identity: str = ""
    value: str = ""


class BindingVisitor(ast.NodeVisitor):
    """Resolve names at their use sites without importing inspected code."""

    def __init__(self) -> None:
        """Start a traversal with independent scope and annotation state."""
        self.bindings: dict[str, Binding] = {}
        self.contracts: dict[str, str] = {}
        self.parents: list[ast.AST] = []
        self.functions: list[FunctionNode] = []

    def visit(self, node: ast.AST) -> None:
        """Expose the active ancestry while preserving normal visitor dispatch."""
        self.parents.append(node)
        try:
            super().visit(node)
        finally:
            self.parents.pop()

    def qualified(self, node: ast.AST | None) -> str:
        """Resolve identities independently of inferred value categories."""
        if isinstance(node, ast.Name):
            binding = self.bindings.get(node.id)
            return node.id if binding is None else binding.identity
        if isinstance(node, ast.Attribute):
            return f"{self.qualified(node.value)}.{node.attr}"
        return ""

    def annotation(self, node: ast.expr | None) -> str:
        """Resolve ordinary, generic, and quoted outer annotation names."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):

            # Invalid forward references have no reliable identity.
            try:
                node = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return ""

        # Generic arguments do not change the outer annotation's identity.
        if isinstance(node, ast.Subscript):
            node = node.value
        return self.qualified(node)

    def annotation_kind(self, _node: ast.expr | None) -> str:
        """Leave value classification to the domain analyzer."""
        return ""

    def kind(self, node: ast.AST | None) -> str:
        """Propagate local values through names and await expressions."""
        if isinstance(node, ast.Name):
            return self.bindings.get(node.id, Binding()).value
        if isinstance(node, ast.Await):
            return self.kind(node.value)
        return ""

    def visit_Import(self, node: ast.Import) -> None:
        """Record import identities with Python's module alias semantics."""
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.bindings[name] = Binding(identity=alias.name if alias.asname else name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Resolve absolute imports and leave relative identities unknown."""
        for alias in node.names:
            identity = f"{node.module}.{alias.name}" if not node.level else ""
            self.bindings[alias.asname or alias.name] = Binding(identity=identity)

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Isolate parameter bindings and restore the enclosing scope on exit."""
        outer, contracts = self.bindings.copy(), self.contracts.copy()
        self.contracts = {}
        self.bindings[node.name] = Binding()
        self.functions.append(node)

        # Parameters shadow outer bindings, including unannotated names.
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        arguments += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
        try:
            for argument in arguments:
                self.bindings[argument.arg] = Binding(value=self.annotation_kind(argument.annotation))

            # Explicit mutable contracts must survive domain value classification.
            for argument in arguments:
                self.contracts[argument.arg] = self.annotation(argument.annotation)

            # Traverse the body only after all parameter contracts are established.
            for statement in node.body:
                self.visit(statement)
        finally:
            self.functions.pop()
            self.bindings, self.contracts = outer, contracts
        self.bindings[node.name] = Binding()

    visit_AsyncFunctionDef = visit_FunctionDef

    def bind(self, target: ast.expr | None, value: str) -> None:
        """Bind simple values and clear unknown unpacked targets."""
        if isinstance(target, ast.Name):
            self.bindings[target.id] = Binding(value=value)
        elif isinstance(target, (ast.Tuple, ast.List)):

            # Unpacking does not preserve the source value's database provenance.
            for element in target.elts:
                self.bind(element, "")

    def visit_Assign(self, node: ast.Assign) -> None:
        """Evaluate uses before replacing assignment targets."""
        self.generic_visit(node)
        for target in node.targets:
            self.bind(target, self.kind(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Retain explicit contracts independently of inferred values."""
        self.generic_visit(node)
        value = self.kind(node.value) if node.value else self.annotation_kind(node.annotation)
        self.bind(node.target, value)
        if isinstance(node.target, ast.Name):
            self.contracts[node.target.id] = self.annotation(node.annotation)

    def visit_If(self, node: ast.If) -> None:
        """Retain only facts shared by both branch outcomes."""
        self.visit(node.test)
        before, contracts_before = self.bindings.copy(), self.contracts.copy()
        for statement in node.body:
            self.visit(statement)
        body, body_contracts = self.bindings.copy(), self.contracts.copy()
        self.bindings, self.contracts = before, contracts_before

        # Branch-local certainty must not become a false-positive after the merge.
        for statement in node.orelse:
            self.visit(statement)
        self.bindings = merge(body, self.bindings, Binding())
        self.contracts = merge(body_contracts, self.contracts, "@unknown")

    def visit_For(self, node: LoopNode) -> None:
        """Account for target shadowing and the zero-iteration path."""
        self.visit(node.iter)

        # Zero iterations retain the incoming bindings; loop targets may shadow them.
        before = self.bindings.copy()
        self.bind(node.target, "")
        for statement in node.body:
            self.visit(statement)
        self.bindings = merge(before, self.bindings, Binding())
        for statement in node.orelse:
            self.visit(statement)

    visit_AsyncFor = visit_For

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Prevent class-local bindings from leaking into adjacent definitions."""
        outer, contracts = self.bindings.copy(), self.contracts.copy()
        try:
            self.generic_visit(node)
        finally:
            self.bindings, self.contracts = outer, contracts
        self.bindings[node.name] = Binding(identity=node.name)

    def visit_With(self, node: WithNode) -> None:
        """Bind context-manager values using the current domain's classifier."""
        for item in node.items:
            self.visit(item.context_expr)
            self.bind(item.optional_vars, self.kind(item.context_expr))
        for statement in node.body:
            self.visit(statement)

    visit_AsyncWith = visit_With
