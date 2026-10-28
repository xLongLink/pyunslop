import ast
from .api import HTTP_METHODS, ROUTER_TYPES, is_raw_response
from .rules import AST_RULES
from .contracts import LoopNode, WithNode, ASTFinding, FunctionNode, ComprehensionNode
from .rules.py010 import is_success_envelope
from .rules.py014 import uses_cli_doc

SESSION_TYPES = {
    "sqlalchemy.orm.Session",
    "sqlalchemy.orm.session.Session",
    "sqlalchemy.engine.Connection",
    "sqlalchemy.engine.base.Connection",
    # Async execute/scalars results are distinct from explicit streaming APIs.
    "sqlalchemy.ext.asyncio.AsyncSession",
    "sqlalchemy.ext.asyncio.session.AsyncSession",
    "sqlalchemy.ext.asyncio.AsyncConnection",
    "sqlalchemy.ext.asyncio.engine.AsyncConnection",
    "sqlmodel.Session",
    "sqlmodel.orm.session.Session",
    "sqlmodel.ext.asyncio.session.AsyncSession",
}

# Factory calls return session constructors, not query results.
FACTORIES = {
    "sqlalchemy.orm.sessionmaker",
    "sqlalchemy.orm.session.sessionmaker",
    "sqlalchemy.ext.asyncio.async_sessionmaker",
    "sqlalchemy.ext.asyncio.session.async_sessionmaker",
}
QUERY_METHODS = {"execute", "scalars", "stream", "stream_scalars", "exec"}
RESULT_TRANSFORMS = {"scalars", "mappings", "unique", "tuples", "columns", "yield_per"}

# Result provenance must originate in a recognized annotation or library call.
RESULT_TYPES = {"Result", "ScalarResult", "MappingResult", "CursorResult", "AsyncResult", "AsyncScalarResult", "AsyncMappingResult"}
EXECUTE_RESULTS = {"@execute_result", "@single_execute_result"}
BUFFERED_RESULTS = {"@result", *EXECUTE_RESULTS}
RESULT_KINDS = {*BUFFERED_RESULTS, "@stream_result"}
SELECT_FUNCTIONS = {"sqlalchemy.select", "sqlalchemy.sql.select", "sqlmodel.select"}

# Expression constructors establish SQL ownership without guessing model attributes.
EXPRESSION_FUNCTIONS = {
    "sqlmodel.col",
    "sqlalchemy.column",
    "sqlalchemy.sql.column",
    "sqlalchemy.literal_column",
    "sqlalchemy.literal",
    "sqlalchemy.and_",
    "sqlalchemy.or_",
    "sqlalchemy.not_",
}

# These modifiers retain the known selection shape rather than introducing columns.
STATEMENT_METHODS = {"where", "filter", "having", "order_by", "group_by", "limit", "offset", "join"}


def check_patterns(tree: ast.AST) -> list[ASTFinding]:
    """Run registered AST rules through one shared scope-aware traversal."""
    visitor = AnalysisVisitor()
    visitor.visit(tree)
    return visitor.findings


class AnalysisVisitor(ast.NodeVisitor):
    """Own traversal, import provenance, and scope facts shared by rule modules."""

    # Independent rules use the same provenance categories as the shared analyzer.
    RESULT_KINDS = RESULT_KINDS
    BUFFERED_RESULTS = BUFFERED_RESULTS
    EXECUTE_RESULTS = EXECUTE_RESULTS
    EXPRESSION_FUNCTIONS = EXPRESSION_FUNCTIONS

    def __init__(self) -> None:
        """Start an independent analysis without retaining state between files."""
        self.cli_doc_used = False
        self.names: dict[str, str] = {}
        self.contracts: dict[str, str] = {}
        self.parents: list[ast.AST] = []
        self.functions: list[FunctionNode] = []
        self.findings: list[ASTFinding] = []

        # Endpoint contracts and deduplication survive nested scope traversal.
        self.reported_returns: set[int] = set()
        self.routes: dict[int, list[ast.Call]] = {}
        self.raw_returns: dict[int, list[bool]] = {}
        self.reported_bindings: set[int] = set()
        self.collection_hooks = False
        self.response_models: dict[int, set[str]] = {}
        self.transforming_models: set[str] = set()

    def visit(self, node: ast.AST) -> None:
        """Maintain parent identity while visiting each node exactly once."""
        self.parents.append(node)
        try:
            super().visit(node)
        finally:
            self.parents.pop()

    def visit_Module(self, node: ast.Module) -> None:
        """Collect module facts before children and evaluate exit rules last."""
        for check in AST_RULES["module"]:
            check(node, self)
        self.collection_hooks = any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name in {"pytest_generate_tests", "pytest_collection_modifyitems"}
            for item in node.body
        )

        # Exit rules need facts discovered anywhere in the module body.
        self.generic_visit(node)
        for check in AST_RULES["module_exit"]:
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
        if name in SESSION_TYPES:
            return "@session"
        if name in ROUTER_TYPES:
            return "@router"
        if is_raw_response(name):
            return "@response"

        # Streaming annotations remain distinct from synchronous result types.
        module, _, symbol = name.rpartition(".")
        if (module == "sqlalchemy" or module.startswith("sqlalchemy.")) and symbol in RESULT_TYPES:
            return "@stream_result" if symbol.startswith("Async") else "@result"
        return ""

    def kind(self, node: ast.AST | None) -> str:
        """Propagate local provenance only through recognized library operations."""
        if is_success_envelope(node, self.qualified):
            return "@envelope"
        if isinstance(node, ast.Name):
            return self.names.get(node.id, "")
        if isinstance(node, ast.Await):
            return self.kind(node.value)
        if not isinstance(node, ast.Call):
            return ""

        # Constructors and factories are resolved by imported identity.
        name = self.qualified(node.func)
        if name in SESSION_TYPES or self.kind(node.func) == "@factory":
            return "@session"
        if name in FACTORIES:
            return "@factory"
        if name in SELECT_FUNCTIONS:
            return "@single_statement" if len(node.args) == 1 and not isinstance(node.args[0], ast.Starred) else "@statement"
        if name in EXPRESSION_FUNCTIONS:
            return "@expression"

        # Raw response objects bypass normal response serialization.
        if name in ROUTER_TYPES:
            return "@router"
        if is_raw_response(name):
            return "@response"
        if isinstance(node.func, ast.Attribute):
            return self.method_kind(node.func, node.args)
        return ""

    def method_kind(self, method: ast.Attribute, arguments: list[ast.expr]) -> str:
        """Preserve buffering and selection shape through documented result methods."""
        owner = self.kind(method.value)
        if owner == "@session" and method.attr in QUERY_METHODS:
            if method.attr == "execute":
                single = bool(arguments) and self.kind(arguments[0]) == "@single_statement"
                return "@single_execute_result" if single else "@execute_result"
            return "@stream_result" if method.attr.startswith("stream") else "@result"

        # Scalar transformations consume execute provenance without losing buffering.
        if owner in RESULT_KINDS and method.attr in RESULT_TRANSFORMS:
            if owner in EXECUTE_RESULTS and method.attr == "scalars":
                return "@result"
            return "@stream_result" if method.attr == "yield_per" else owner
        if owner in RESULT_KINDS and method.attr in {"all", "fetchall"}:
            return "@rows"
        if owner in {"@statement", "@single_statement"} and method.attr in STATEMENT_METHODS:
            return owner
        return ""

    def visit_Import(self, node: ast.Import) -> None:
        """Evaluate import rules before updating local aliases."""
        for check in AST_RULES["import"]:
            check(node, self)
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.names[name] = alias.name if alias.asname else name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track absolute import identities and conservatively forget relative ones."""
        for check in AST_RULES["import"]:
            check(node, self)
        for alias in node.names:
            self.names[alias.asname or alias.name] = f"{node.module}.{alias.name}" if not node.level else ""

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Analyze endpoint contracts outside parameter-local bindings."""
        for check in AST_RULES["function"]:
            check(node, self)
        self.routes[id(node)] = self.route_decorators(node)

        # Resolve decorator model aliases before parameters can shadow their names.
        self.response_models[id(node)] = {
            self.qualified(keyword.value)
            for route in self.routes[id(node)]
            for keyword in route.keywords
            if keyword.arg == "response_model"
        }

        # Parameters shadow outer bindings, including unannotated names.
        self.raw_returns[id(node)] = []
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
        for check in AST_RULES["function_exit"]:
            check(node, self)
        self.names[node.name] = ""

    visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

    def route_decorators(self, node: FunctionNode) -> list[ast.Call]:
        """Identify HTTP route decorators owned by known FastAPI routers."""
        return [
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in HTTP_METHODS
            and self.kind(decorator.func.value) == "@router"
        ]

    def bind(self, target: ast.expr | None, kind: str) -> None:
        """Track simple aliases while clearing unknown unpacked values."""
        if isinstance(target, ast.Name):
            self.names[target.id] = kind
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.bind(element, "")

    def visit_Assign(self, node: ast.Assign) -> None:
        """Evaluate assignment rules before rebinding query or client aliases."""
        for check in AST_RULES["assign"]:
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
        for check in AST_RULES["for"]:
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
        self.record_model_transformations(node)
        for check in AST_RULES["class"]:
            check(node, self)
        outer, contracts = self.names.copy(), self.contracts.copy()
        self.generic_visit(node)
        self.names, self.contracts = outer, contracts
        self.names[node.name] = node.name

    def record_model_transformations(self, node: ast.ClassDef) -> None:
        """Record visible validators and initialization hooks for response reviews."""
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = [decorator.func if isinstance(decorator, ast.Call) else decorator for decorator in method.decorator_list]

            # Custom initialization and validators can intentionally transform a response.
            if method.name in {"model_validate", "model_post_init", "__init__"} or any(
                self.qualified(decorator)
                in {"pydantic.field_validator", "pydantic.model_validator", "pydantic.validator", "pydantic.root_validator"}
                for decorator in decorators
            ):
                self.transforming_models.add(node.name)

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
        for check in AST_RULES["attribute"]:
            check(node, self)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Collect response provenance before evaluating return-site rules."""
        if self.functions:
            self.raw_returns[id(self.functions[-1])].append(self.kind(node.value) == "@response")
        for check in AST_RULES["return"]:
            check(node, self)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Collect CLI-help provenance and evaluate independent call-site rules."""
        self.cli_doc_used |= uses_cli_doc(node, self.qualified)
        for check in AST_RULES["call"]:
            check(node, self)
        self.generic_visit(node)

    def visit_ListComp(self, node: ComprehensionNode) -> None:
        """Evaluate comprehension rules without revisiting their children."""
        for check in AST_RULES["comprehension"]:
            check(node, self)
        self.generic_visit(node)

    visit_SetComp = visit_ListComp  # noqa: N815
    visit_DictComp = visit_ListComp  # noqa: N815
    visit_GeneratorExp = visit_ListComp  # noqa: N815

    def visit_Expr(self, node: ast.Expr) -> None:
        """Evaluate statement-boundary rules such as post-commit refresh reviews."""
        for check in AST_RULES["expression"]:
            check(node, self)
        self.generic_visit(node)
