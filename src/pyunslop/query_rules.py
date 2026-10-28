import ast

from .api_rules import (
    HTTP_METHODS, ROUTER_TYPES, is_external, is_raw_response,
    is_success_envelope, needs_response_model,
)
from .review_rules import (
    borrowed_client_class, comprehension_dependencies, empty_subclass,
    forwarded_function, iterable_materialization, method_call, only_size_uses,
    single_literal_case, single_use_constants, size_use, temporary_iterable_pair, uses_cli_doc,
)

SESSION_TYPES = {
    "sqlalchemy.orm.Session", "sqlalchemy.orm.session.Session",
    "sqlalchemy.engine.Connection", "sqlalchemy.engine.base.Connection",
    "sqlalchemy.ext.asyncio.AsyncSession", "sqlalchemy.ext.asyncio.session.AsyncSession",
    "sqlalchemy.ext.asyncio.AsyncConnection", "sqlalchemy.ext.asyncio.engine.AsyncConnection",
    "sqlmodel.Session", "sqlmodel.orm.session.Session",
    "sqlmodel.ext.asyncio.session.AsyncSession",
}

# Factory calls produce session constructors, not query results themselves.
FACTORIES = {
    "sqlalchemy.orm.sessionmaker", "sqlalchemy.orm.session.sessionmaker",
    "sqlalchemy.ext.asyncio.async_sessionmaker",
    "sqlalchemy.ext.asyncio.session.async_sessionmaker",
}
QUERY_METHODS = {"execute", "scalars", "stream", "stream_scalars", "exec"}
RESULT_TRANSFORMS = {"scalars", "mappings", "unique", "tuples", "columns", "yield_per"}

# Typed results can originate in helper functions outside the current file.
RESULT_TYPES = {
    "Result", "ScalarResult", "MappingResult", "CursorResult",
    "AsyncResult", "AsyncScalarResult", "AsyncMappingResult",
}
EXECUTE_RESULTS = {"@execute_result", "@single_execute_result"}
BUFFERED_RESULTS = {"@result", *EXECUTE_RESULTS}
RESULT_KINDS = {*BUFFERED_RESULTS, "@stream_result"}

# Only these domain class names require a named instance before method calls.
DOMAIN_CLASSES = {"Postgres", "Kubernetes"}
SELECT_FUNCTIONS = {"sqlalchemy.select", "sqlalchemy.sql.select", "sqlmodel.select"}
EXPRESSION_FUNCTIONS = {
    "sqlmodel.col", "sqlalchemy.column", "sqlalchemy.sql.column",
    "sqlalchemy.literal_column", "sqlalchemy.literal",
    "sqlalchemy.and_", "sqlalchemy.or_", "sqlalchemy.not_",
}
STATEMENT_METHODS = {"where", "filter", "having", "order_by", "group_by", "limit", "offset", "join"}


def check_queries(tree: ast.AST) -> list[tuple[ast.AST, str, str]]:
    visitor = QueryVisitor()
    visitor.visit(tree)
    if isinstance(tree, ast.Module) and ast.get_docstring(tree) is not None and not visitor.cli_doc_used:
        visitor.findings.append((tree.body[0], "PY014", "repository policy forbids leading module docstrings"))
    return visitor.findings


class QueryVisitor(ast.NodeVisitor):
    def __init__(self):
        self.cli_doc_used = False
        self.names: dict[str, str] = {}
        self.contracts: dict[str, str] = {}
        self.parents: list[ast.AST] = []
        self.functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.findings: list[tuple[ast.AST, str, str]] = []

        # Function-level contracts and deduplication outlive each nested traversal.
        self.reported_returns: set[int] = set()
        self.routes: dict[int, list[ast.Call]] = {}
        self.raw_returns: dict[int, list[bool]] = {}
        self.reported_bindings: set[int] = set()
        self.collection_hooks = False
        self.response_models: dict[int, set[str]] = {}
        self.transforming_models: set[str] = set()

    def visit_Module(self, node):
        self.findings.extend(single_use_constants(node))
        self.collection_hooks = any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name in {"pytest_generate_tests", "pytest_collection_modifyitems"}
            for item in node.body
        )
        self.generic_visit(node)

    def visit(self, node):
        self.parents.append(node)
        try:
            return super().visit(node)
        finally:
            self.parents.pop()

    def qualified(self, node):
        if isinstance(node, ast.Name):
            return self.names.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{self.qualified(node.value)}.{node.attr}"
        return ""

    def annotation(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return ""
        if isinstance(node, ast.Subscript):
            node = node.value
        return self.qualified(node)

    def annotation_kind(self, node):
        name = self.annotation(node)
        if name in SESSION_TYPES:
            return "@session"
        if name in ROUTER_TYPES:
            return "@router"
        if is_raw_response(name):
            return "@response"

        # Result annotations still require a known library namespace.
        module, _, symbol = name.rpartition(".")
        if (module == "sqlalchemy" or module.startswith("sqlalchemy.")) and symbol in RESULT_TYPES:
            return "@stream_result" if symbol.startswith("Async") else "@result"
        return ""

    def kind(self, node):
        if is_success_envelope(node, self.qualified):
            return "@envelope"
        if isinstance(node, ast.Name):
            return self.names.get(node.id, "")
        if isinstance(node, ast.Await):
            return self.kind(node.value)
        if not isinstance(node, ast.Call):
            return ""

        # Constructors are recognized by import identity, never by variable spelling.
        name = self.qualified(node.func)
        if name in SESSION_TYPES or self.kind(node.func) == "@factory":
            return "@session"
        if name in FACTORIES:
            return "@factory"
        if name in SELECT_FUNCTIONS:
            return "@single_statement" if len(node.args) == 1 and not isinstance(node.args[0], ast.Starred) else "@statement"
        if name in EXPRESSION_FUNCTIONS:
            return "@expression"

        # Raw responses bypass FastAPI's JSON serialization and response schemas.
        if name in ROUTER_TYPES:
            return "@router"
        if is_raw_response(name):
            return "@response"

        # Propagate only documented result-producing methods, not arbitrary calls.
        if isinstance(node.func, ast.Attribute):
            owner = self.kind(node.func.value)
            if owner == "@session" and node.func.attr in QUERY_METHODS:
                if node.func.attr == "execute":
                    single = node.args and self.kind(node.args[0]) == "@single_statement"
                    return "@single_execute_result" if single else "@execute_result"
                return "@stream_result" if node.func.attr.startswith("stream") else "@result"

            # Streaming results stay streaming through result transformations.
            if owner in RESULT_KINDS and node.func.attr in RESULT_TRANSFORMS:
                if owner in EXECUTE_RESULTS and node.func.attr == "scalars":
                    return "@result"
                return "@stream_result" if node.func.attr == "yield_per" else owner
            if owner in RESULT_KINDS and node.func.attr in {"all", "fetchall"}:
                return "@rows"
            if owner in {"@statement", "@single_statement"} and node.func.attr in STATEMENT_METHODS:
                return owner
        return ""

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "src.errors" or alias.name.startswith("src.errors."):
                self.findings.append((alias, "PY013", "do not import retired src.errors wrappers; use FastAPI HTTPException directly"))
            name = alias.asname or alias.name.split(".")[0]
            self.names[name] = alias.name if alias.asname else name

    def visit_ImportFrom(self, node):
        if not node.level and (
            node.module == "src.errors" or (node.module or "").startswith("src.errors.")
            or (node.module == "src" and any(alias.name == "errors" for alias in node.names))
        ):
            self.findings.append((node, "PY013", "do not import retired src.errors wrappers; use FastAPI HTTPException directly"))
        for alias in node.names:
            self.names[alias.asname or alias.name] = (
                f"{node.module}.{alias.name}" if not node.level else ""
            )

    def visit_FunctionDef(self, node):
        self.findings.extend(single_use_constants(node))
        self.check_function_structure(node)
        self.routes[id(node)] = self.route_decorators(node)
        self.response_models[id(node)] = {
            self.qualified(keyword.value) for route in self.routes[id(node)]
            for keyword in route.keywords if keyword.arg == "response_model"
        }

        # Capture decorator contracts before parameters shadow imported model names.
        self.raw_returns[id(node)] = []
        outer = self.names.copy()
        outer_contracts = self.contracts.copy()
        self.contracts = {}
        self.names[node.name] = ""
        self.functions.append(node)

        # Parameters shadow outer bindings, even when they lack annotations.
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        arguments += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
        for argument in arguments:
            self.names[argument.arg] = self.annotation_kind(argument.annotation)

        # Argument annotations seed this scope without leaking into sibling functions.
        for argument in arguments:
            self.contracts[argument.arg] = self.annotation(argument.annotation)
        for statement in node.body:
            self.visit(statement)

        # Route options and return annotations resolve in the definition scope.
        self.functions.pop()
        self.names = outer
        self.contracts = outer_contracts
        self.check_response_models(node)
        self.names[node.name] = ""

    visit_AsyncFunctionDef = visit_FunctionDef

    def check_function_structure(self, node):
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if not self.collection_hooks and not any(argument.arg == "request" for argument in args):
            for decorator in node.decorator_list:
                if single_literal_case(decorator, self.qualified):
                    self.findings.append((decorator, "PY015", "replace single literal-case parametrization with a direct test"))

        # Private inherited methods may be framework hooks rather than expendable wrappers.
        parent = self.parents[-2] if len(self.parents) > 1 else None
        framework_method = isinstance(parent, ast.ClassDef) and (parent.bases or parent.decorator_list)
        if not framework_method and forwarded_function(node):
            self.findings.append((node, "PY110", "review this transparent forwarding wrapper; preserve public contracts and meaningful boundaries"))

    def route_decorators(self, node):
        return [
            decorator for decorator in node.decorator_list
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in HTTP_METHODS
            and self.kind(decorator.func.value) == "@router"
        ]

    def check_response_models(self, node):
        returns = self.raw_returns[id(node)]
        if self.annotation_kind(node.returns) == "@response" or (returns and all(returns)):
            return
        for route in self.routes[id(node)]:
            if needs_response_model(route, self.qualified):
                self.findings.append((
                    route, "PY009", "declare response_model explicitly for this JSON endpoint",
                ))

    def bind(self, target, kind):
        if isinstance(target, ast.Name):
            self.names[target.id] = kind
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.bind(element, "")

    def visit_Assign(self, node):
        self.check_temporary_iterable(node)
        for target in node.targets:
            if isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == 1 and self.single_row_call(node.value):
                self.findings.append((target, "PY108", "use session.scalars() for single-column row unpacking; preserve the existing cardinality check"))
        self.generic_visit(node)
        for target in node.targets:
            self.bind(target, self.kind(node.value))

    def check_temporary_iterable(self, node):
        if not self.functions:
            return
        parent = self.parents[-2]

        # Analyze here so earlier rebindings of iterable consumers are respected.
        for _, statements in ast.iter_fields(parent):
            if not isinstance(statements, list) or node not in statements:
                continue
            index = statements.index(node)
            if index + 1 < len(statements):
                self.findings.extend(temporary_iterable_pair(
                    self.functions[-1], node, statements[index + 1], self.qualified,
                ))

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        kind = self.kind(node.value) if node.value else self.annotation_kind(node.annotation)
        self.bind(node.target, kind)
        if isinstance(node.target, ast.Name):
            self.contracts[node.target.id] = self.annotation(node.annotation)

    def visit_If(self, node):
        self.visit(node.test)
        before = self.names.copy()
        contracts_before = self.contracts.copy()
        for statement in node.body:
            self.visit(statement)
        body = self.names.copy()
        body_contracts = self.contracts.copy()
        self.names = before
        self.contracts = contracts_before

        # After a branch, only provenance shared by both paths is trustworthy.
        for statement in node.orelse:
            self.visit(statement)
        self.names = self.merge(body, self.names, "")
        self.contracts = self.merge(body_contracts, self.contracts, "@unknown")

    @staticmethod
    def merge(left, right, unknown):
        return {
            name: left[name] if name in left and left[name] == right.get(name) else unknown
            for name in left.keys() | right.keys()
        }

    def visit_For(self, node):
        if type(node) is ast.For and self.is_buffered_all(node.iter):
            self.findings.append((
                node.iter, "PY004", "iterate the buffered query result directly instead of calling all()",
            ))
        if isinstance(node.target, (ast.Tuple, ast.List)) and len(node.target.elts) == 1 and self.kind(node.iter) == "@single_execute_result":
            self.findings.append((node.target, "PY108", "use session.scalars() for this single-column query; preserve cardinality checks"))
        self.visit(node.iter)

        # A loop may execute zero times, so merge its bindings with the entry state.
        before = self.names.copy()
        self.bind(node.target, "")
        for statement in node.body:
            self.visit(statement)
        self.names = self.merge(before, self.names, "")
        for statement in node.orelse:
            self.visit(statement)

    visit_AsyncFor = visit_For

    def visit_ClassDef(self, node):
        self.record_model_transformations(node)
        if empty_subclass(node, self.qualified):
            self.findings.append((node, "PY110", "review this subclass with no added behavior; preserve framework hooks and public contracts"))
        if borrowed_client_class(node):
            self.findings.append((node, "PY111", "review this borrowed-client-only class as namespaced functions; preserve meaningful boundaries"))

        # Class-local imports must not leak into the module or neighboring classes.
        outer = self.names.copy()
        contracts = self.contracts.copy()
        self.generic_visit(node)
        self.names = outer
        self.contracts = contracts
        self.names[node.name] = node.name

    def record_model_transformations(self, node):
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = [decorator.func if isinstance(decorator, ast.Call) else decorator for decorator in method.decorator_list]
            if method.name in {"model_validate", "model_post_init", "__init__"} or any(
                self.qualified(decorator) in {"pydantic.field_validator", "pydantic.model_validator", "pydantic.validator", "pydantic.root_validator"}
                for decorator in decorators
            ):
                self.transforming_models.add(node.name)

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            self.bind(item.optional_vars, self.kind(item.context_expr))
        for statement in node.body:
            self.visit(statement)

    visit_AsyncWith = visit_With

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Await) and self.kind(node.value) in RESULT_KINDS:
            self.findings.append((
                node, "PY001", "name the asynchronous query result before consuming it",
            ))
        self.generic_visit(node)

    def is_copy(self, node):
        return (
            isinstance(node, ast.Call) and self.qualified(node.func) == "list"
            and len(node.args) == 1 and not node.keywords
            and isinstance(node.args[0], ast.Call) and self.kind(node.args[0]) == "@rows"
        )

    def visit_Return(self, node):
        if self.functions:
            function = self.functions[-1]
            self.check_api_return(function, node)
            contract = self.annotation(function.returns)
            if contract in {"list", "typing.List"} and (
                self.kind(node.value) == "@rows" or self.is_copy(node.value)
            ) and id(function) not in self.reported_returns:
                self.reported_returns.add(id(function))

                # Point at the contract to change, not at each return statement.
                self.findings.append((
                    function.returns, "PY002",
                    "use Sequence[T] for a read-only query-result return type",
                ))
        self.generic_visit(node)

    def check_api_return(self, function, node):
        self.raw_returns[id(function)].append(self.kind(node.value) == "@response")
        routes = self.routes[id(function)]
        if routes and not any(is_external(route) for route in routes):
            self.check_response_validation(routes, node)
            if self.kind(node.value) == "@envelope":
                self.findings.append((
                    node.value, "PY010", "return the API payload directly instead of a generic success envelope",
                ))

    def check_response_validation(self, routes, node):
        value = node.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "model_validate"):
            return
        if len(value.args) != 1 or value.keywords or not isinstance(value.args[0], (ast.Name, ast.Attribute)):
            return
        model = self.qualified(value.func.value)
        function = self.functions[-1]
        if model and model not in self.transforming_models and self.response_models[id(function)] == {model}:
            self.findings.append((value, "PY101", "route already validates this response model; avoid reconstruction unless validation intentionally transforms it"))

    def single_row_call(self, node):
        return (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"one", "one_or_none", "first"}
            and self.kind(node.func.value) == "@single_execute_result"
        )

    def accepts_sequence(self, parent):
        if isinstance(parent, ast.Assign):
            return all(
                isinstance(target, ast.Name) and self.contracts.get(target.id, "") in {
                    "", "typing.Sequence", "collections.abc.Sequence",
                }
                for target in parent.targets
            )
        if isinstance(parent, ast.AnnAssign):
            return self.annotation(parent.annotation) in {"typing.Sequence", "collections.abc.Sequence"}

        # An unknown callee or return contract may genuinely require a mutable list.
        if isinstance(parent, ast.Return) and self.functions:
            return self.annotation(self.functions[-1].returns) in {
                "typing.Sequence", "collections.abc.Sequence",
            }
        return False

    def is_buffered_all(self, node):
        return (
            isinstance(node, ast.Call) and not node.args and not node.keywords
            and isinstance(node.func, ast.Attribute) and node.func.attr == "all"
            and self.kind(node.func.value) in BUFFERED_RESULTS
        )

    def in_expression_context(self):
        for parent in reversed(self.parents[:-1]):
            if isinstance(parent, ast.Call):
                if self.qualified(parent.func) in EXPRESSION_FUNCTIONS:
                    return True

                # Never infer SQL expression semantics through an unrelated call.
                return (
                    isinstance(parent.func, ast.Attribute)
                    and parent.func.attr in {"where", "filter", "having"}
                    and self.kind(parent.func.value) in {"@statement", "@single_statement"}
                )
        return False

    def check_in_comprehension(self, node):
        if not (
            isinstance(node.func, ast.Attribute) and node.func.attr == "in_"
            and len(node.args) == 1 and isinstance(node.args[0], ast.ListComp)
            and not node.keywords
        ):
            return

        # An arbitrary method named in_ need not accept a generator.
        if self.kind(node.func.value) == "@expression" or self.in_expression_context():
            self.findings.append((
                node.args[0], "PY005", "pass a generator expression directly to SQLAlchemy in_()",
            ))

    def check_domain_chain(self, node):
        if not isinstance(node.func, ast.Attribute):
            return
        owner = node.func.value

        # Walk property access such as .applications.logs back to its constructor.
        while isinstance(owner, ast.Attribute):
            owner = owner.value
        if isinstance(owner, ast.Call):
            name = self.qualified(owner.func).rsplit(".", 1)[-1]
            if name in DOMAIN_CLASSES:
                self.findings.append((
                    owner, "PY006", f"assign the {name} instance to a name before calling its methods",
                ))

    def visit_Call(self, node):
        self.cli_doc_used |= uses_cli_doc(node, self.qualified)
        parent = self.parents[-2] if len(self.parents) > 1 else None
        if self.is_copy(node) and self.accepts_sequence(parent):
            self.findings.append((
                node, "PY003", "avoid list() around query-result rows when a sequence is sufficient",
            ))

        # These independent reviews share the same import and query provenance.
        self.check_in_comprehension(node)
        self.check_domain_chain(node)
        self.check_query_consumption(node)
        if iterable_materialization(node, self.qualified):
            self.findings.append((node.args[0], "PY107", "review a generator for this iterable-only consumer; preserve snapshot and exception timing"))
        self.generic_visit(node)

    def check_query_consumption(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "scalars" and self.kind(node.func.value) in EXECUTE_RESULTS:
            self.findings.append((node, "PY108", "use session.scalars() instead of execute().scalars(); preserve one()/one_or_none() cardinality checks"))
        if self.kind(node) != "@rows" or len(self.parents) < 2:
            return
        parent = self.parents[-2]
        candidate = size_use(node, parent, self.qualified)

        # Named rows qualify only when every use is a size or truth operation.
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) and self.functions:
            candidate = only_size_uses(self.functions[-1], parent.targets[0].id, self.qualified)
        if candidate:
            self.findings.append((node, "PY109", "review an existence or bounded query instead of loading rows solely for size/truth; preserve locking"))

    def visit_ListComp(self, node):
        for binding in comprehension_dependencies(node):
            if id(binding) not in self.reported_bindings:
                self.reported_bindings.add(id(binding))
                self.findings.append((binding, "PY106", "use an explicit loop when a comprehension's constructor arguments depend on a walrus binding"))
        self.generic_visit(node)

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_Expr(self, node):
        refresh = method_call(node)
        if refresh and refresh.func.attr == "refresh" and self.kind(refresh.func.value) == "@session":
            self.check_refresh(node, refresh)
        self.generic_visit(node)

    def check_refresh(self, node, refresh):
        parent = self.parents[-2]
        for _, statements in ast.iter_fields(parent):
            if not isinstance(statements, list) or node not in statements:
                continue
            index = statements.index(node)
            commit = method_call(statements[index - 1]) if index else None
            if commit and commit.func.attr == "commit" and ast.dump(commit.func.value) == ast.dump(refresh.func.value):
                self.findings.append((node, "PY113", "review post-commit refresh: check expire_on_commit, server defaults, and required relationships before removing it"))
