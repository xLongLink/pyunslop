import ast
from . import queries
from .api import ROUTER_TYPES, route_decorators
from .rules import ast_rules
from .contracts import LoopNode, WithNode, ASTFinding, FunctionNode, ComprehensionNode


def check_patterns(tree: ast.AST, source: str = "") -> list[ASTFinding]:
    """Run registered AST rules through one shared scope-aware traversal."""
    visitor = AnalysisVisitor(source)
    visitor.visit(tree)
    return visitor.findings


class AnalysisVisitor(ast.NodeVisitor):
    """Own traversal, import provenance, and scope facts shared by rule modules."""

    def __init__(self, source: str = "") -> None:
        """Start an independent analysis without retaining state between files."""
        self.rules = ast_rules()
        self.source_lines = source.splitlines()
        self.names: dict[str, str] = {}
        self.contracts: dict[str, str] = {}
        self.parents: list[ast.AST] = []
        self.functions: list[FunctionNode] = []
        self.findings: list[ASTFinding] = []

        self.routes: dict[int, list[ast.Call]] = {}

    def visit(self, node: ast.AST) -> None:
        """Maintain parent identity while visiting each node exactly once."""
        self.parents.append(node)
        try:
            super().visit(node)
        finally:
            self.parents.pop()

    def visit_Module(self, node: ast.Module) -> None:
        """Collect module facts before children and evaluate exit rules last."""
        for check in self.rules["module"]:
            check(node, self)

        # Exit rules need facts discovered anywhere in the module body.
        self.generic_visit(node)
        for check in self.rules["module_exit"]:
            check(node, self)

    def qualified(self, node: ast.AST | None) -> str:
        """Resolve known imported names without importing inspected code."""
        if isinstance(node, ast.Name):
            return self.names.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{self.qualified(node.value)}.{node.attr}"
        return ""

    def annotation(self, node: ast.expr | None) -> str:
        """Resolve the outer type of ordinary, generic, or quoted annotations."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return ""
        if isinstance(node, ast.Subscript):
            node = node.value
        return self.qualified(node)

    def annotation_kind(self, node: ast.expr | None) -> str:
        """Classify known session, router, response, and result annotations."""
        name = self.annotation(node)
        if name in ROUTER_TYPES:
            return "@router"
        for classify in self.rules["annotation"]:
            if kind := classify(name):
                return kind

        return queries.annotation_kind(name)

    def kind(self, node: ast.AST | None) -> str:
        """Propagate local provenance only through recognized library operations."""
        if node is None:
            return ""
        for classify in self.rules["kind"]:
            if kind := classify(node, self):
                return kind
        if isinstance(node, ast.Name):
            return self.names.get(node.id, "")

        # Await preserves provenance; only calls can construct new library objects.
        if isinstance(node, ast.Await):
            return self.kind(node.value)
        if not isinstance(node, ast.Call):
            return ""

        if self.qualified(node.func) in ROUTER_TYPES:
            return "@router"
        return queries.kind(node, self)

    def visit_Import(self, node: ast.Import) -> None:
        """Evaluate import rules before updating local aliases."""
        for check in self.rules["import"]:
            check(node, self)
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.names[name] = alias.name if alias.asname else name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track absolute import identities and conservatively forget relative ones."""
        for check in self.rules["import"]:
            check(node, self)
        for alias in node.names:
            self.names[alias.asname or alias.name] = f"{node.module}.{alias.name}" if not node.level else ""

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Analyze endpoint contracts outside parameter-local bindings."""
        self.routes[id(node)] = route_decorators(node, self)
        for check in self.rules["function"]:
            check(node, self)

        # Parameters shadow outer bindings, including unannotated names.
        outer, outer_contracts = self.names.copy(), self.contracts.copy()
        self.contracts = {}
        self.names[node.name] = ""
        self.functions.append(node)
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        arguments += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
        for argument in arguments:
            self.names[argument.arg] = self.annotation_kind(argument.annotation)

        # Argument contracts and return provenance belong only to this function.
        for argument in arguments:
            self.contracts[argument.arg] = self.annotation(argument.annotation)
        for statement in node.body:
            self.visit(statement)
        self.functions.pop()
        self.names, self.contracts = outer, outer_contracts
        for check in self.rules["function_exit"]:
            check(node, self)
        self.names[node.name] = ""

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

    def bind(self, target: ast.expr | None, kind: str) -> None:
        """Track simple aliases while clearing unknown unpacked values."""
        if isinstance(target, ast.Name):
            self.names[target.id] = kind
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.bind(element, "")

    def visit_Assign(self, node: ast.Assign) -> None:
        """Evaluate assignment rules before rebinding query or client aliases."""
        for check in self.rules["assign"]:
            check(node, self)
        self.generic_visit(node)
        for target in node.targets:
            self.bind(target, self.kind(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Retain explicit assignment contracts and known result annotations."""
        self.generic_visit(node)
        kind = self.kind(node.value) if node.value else self.annotation_kind(node.annotation)
        self.bind(node.target, kind)
        if isinstance(node.target, ast.Name):
            self.contracts[node.target.id] = self.annotation(node.annotation)

    def visit_If(self, node: ast.If) -> None:
        """Keep only provenance common to both possible branch outcomes."""
        self.visit(node.test)
        before, contracts_before = self.names.copy(), self.contracts.copy()
        for statement in node.body:
            self.visit(statement)
        body, body_contracts = self.names.copy(), self.contracts.copy()
        self.names, self.contracts = before, contracts_before

        # Branch-local certainty must not become a false-positive after the merge.
        for statement in node.orelse:
            self.visit(statement)
        self.names = self.merge(body, self.names, "")
        self.contracts = self.merge(body_contracts, self.contracts, "@unknown")

    @staticmethod
    def merge(left: dict[str, str], right: dict[str, str], unknown: str) -> dict[str, str]:
        """Replace conflicting branch bindings with conservative unknown values."""
        return {name: left[name] if name in left and left[name] == right.get(name) else unknown for name in left.keys() | right.keys()}

    def visit_For(self, node: LoopNode) -> None:
        """Account for loop-target shadowing and zero-iteration outcomes."""
        for check in self.rules["for"]:
            check(node, self)
        self.visit(node.iter)

        # Zero iterations retain the incoming bindings; loop targets may shadow them.
        before = self.names.copy()
        self.bind(node.target, "")
        for statement in node.body:
            self.visit(statement)
        self.names = self.merge(before, self.names, "")
        for statement in node.orelse:
            self.visit(statement)

    visit_AsyncFor = visit_For  # noqa: N815

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Keep class-local state from leaking into neighboring definitions."""
        for check in self.rules["class"]:
            check(node, self)
        outer, contracts = self.names.copy(), self.contracts.copy()
        self.generic_visit(node)
        self.names, self.contracts = outer, contracts
        self.names[node.name] = node.name

    def visit_With(self, node: WithNode) -> None:
        """Propagate known session-factory context-manager bindings."""
        for item in node.items:
            self.visit(item.context_expr)
            self.bind(item.optional_vars, self.kind(item.context_expr))
        for statement in node.body:
            self.visit(statement)

    visit_AsyncWith = visit_With  # noqa: N815

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Evaluate attribute rules with their original parent and scope facts."""
        for check in self.rules["attribute"]:
            check(node, self)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Evaluate return-site rules in the current function scope."""
        for check in self.rules["return"]:
            check(node, self)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Evaluate call-site rules with current import aliases."""
        for check in self.rules["call"]:
            check(node, self)
        self.generic_visit(node)

    def visit_ListComp(self, node: ComprehensionNode) -> None:
        """Evaluate comprehension rules without revisiting their children."""
        for check in self.rules["comprehension"]:
            check(node, self)
        self.generic_visit(node)

    visit_SetComp = visit_ListComp  # noqa: N815
    visit_DictComp = visit_ListComp  # noqa: N815
    visit_GeneratorExp = visit_ListComp  # noqa: N815

    def visit_Expr(self, node: ast.Expr) -> None:
        """Evaluate statement-boundary rules such as post-commit refresh reviews."""
        for check in self.rules["expression"]:
            check(node, self)
        self.generic_visit(node)
