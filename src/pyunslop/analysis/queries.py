import ast
from pyunslop.analysis import query_types
from pyunslop.ast_utils import name_loads, scope_nodes, statement_positions
from pyunslop.contracts import LoopNode, FunctionNode
from pyunslop.diagnostics import Finding
from pyunslop.analysis.bindings import BindingVisitor

SCALAR_API_MESSAGE = "use session.scalars() instead of execute().scalars(); preserve one()/one_or_none() cardinality checks"
REFRESH_MESSAGE = "review post-commit refresh: check expire_on_commit, server defaults, and required relationships before removing it"


class QueryAnalyzer(BindingVisitor):
    """Own SQLAlchemy/SQLModel provenance and all query-related diagnostics."""

    def __init__(self) -> None:
        """Keep result provenance and return deduplication local to this file."""
        super().__init__()
        self.findings: list[Finding] = []
        self.reported_returns: set[FunctionNode] = set()

    def annotation_kind(self, node: ast.expr | None) -> str:
        """Recognize session and result annotations."""
        return query_types.annotation_kind(self.annotation(node))

    def kind(self, node: ast.AST | None) -> str:
        """Classify only known database operations and locally bound values."""
        return query_types.kind(node, self) if isinstance(node, ast.Call) else super().kind(node)

    def is_copy(self, node: ast.AST | None) -> bool:
        """Recognize builtin list conversions around known query rows."""
        return (
            isinstance(node, ast.Call)
            and self.qualified(node.func) == "list"
            and len(node.args) == 1
            and not node.keywords
            and isinstance(node.args[0], ast.Call)
            and self.kind(node.args[0]) == "@rows"
        )

    def accepts_sequence(self, parent: ast.AST | None) -> bool:
        """Preserve copies required by mutable or unknown contracts."""
        if isinstance(parent, ast.Assign):
            return all(
                isinstance(target, ast.Name) and self.contracts.get(target.id, "") in {"", "typing.Sequence", "collections.abc.Sequence"}
                for target in parent.targets
            )

        # An explicit annotation takes precedence over inferred assignment usage.
        if isinstance(parent, ast.AnnAssign):
            return self.annotation(parent.annotation) in {"typing.Sequence", "collections.abc.Sequence"}

        # Unknown return types and consumers may require actual mutable lists.
        if isinstance(parent, ast.Return) and self.functions:
            return self.annotation(self.functions[-1].returns) in {"typing.Sequence", "collections.abc.Sequence"}
        return False

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Identify unnamed asynchronous query results."""
        if isinstance(node.value, ast.Await) and self.kind(node.value) in query_types.RESULT_KINDS:
            self.findings.append(Finding.at(node, "SLOP004", "name the asynchronous query result before consuming it"))
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Report each mutable query-row return contract once."""
        if self.functions:
            function = self.functions[-1]

            # Point to the contract once, even when several returns have the same issue.
            if (
                self.annotation(function.returns) in {"list", "typing.List"}
                and (self.kind(node.value) == "@rows" or self.is_copy(node.value))
                and function not in self.reported_returns
                and function.returns is not None
            ):
                self.reported_returns.add(function)
                self.findings.append(Finding.at(function.returns, "SLOP005", "use Sequence[T] for a read-only query-result return type"))

        # Return expressions may contain additional query operations.
        self.generic_visit(node)

    def visit_For(self, node: LoopNode) -> None:
        """Review buffered iteration and single-column row unpacking."""
        iterable = node.iter

        # Async iteration and argument-bearing calls retain their existing semantics.
        if (
            type(node) is ast.For
            and isinstance(iterable, ast.Call)
            and not iterable.args
            and not iterable.keywords
            and isinstance(iterable.func, ast.Attribute)
            and iterable.func.attr == "all"
            # Unknown or streaming results must retain their materialization semantics.
            and self.kind(iterable.func.value) in query_types.BUFFERED_RESULTS
        ):
            self.findings.append(Finding.at(iterable, "SLOP007", "iterate the buffered query result directly instead of calling all()"))

        # One-column unpacking preserves a distinct cardinality contract.
        if (
            isinstance(node.target, (ast.Tuple, ast.List))
            and len(node.target.elts) == 1
            and self.kind(node.iter) == "@single_execute_result"
        ):
            self.findings.append(
                Finding.at(node.target, "SLOP018", "use session.scalars() for this single-column query; preserve cardinality checks")
            )

        # Bind loop targets only after checking the incoming query provenance.
        super().visit_For(node)

    visit_AsyncFor = visit_For

    def visit_Assign(self, node: ast.Assign) -> None:
        """Review one-column unpacking before assignment changes provenance."""
        value = node.value
        single_row = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr in {"one", "one_or_none", "first"}
            and self.kind(value.func.value) == "@single_execute_result"
        )

        # One-element unpacking is eligible; multi-column row contracts stay intact.
        for target in node.targets:
            if isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == 1 and single_row:

                # Keep the one/first consumer's cardinality requirement in the warning.
                self.findings.append(
                    Finding.at(
                        target, "SLOP018", "use session.scalars() for single-column row unpacking; preserve the existing cardinality check"
                    )
                )

        # Assignment may overwrite the result name used by the checks above.
        super().visit_Assign(node)

    def in_expression_context(self) -> bool:
        """Require SQL ownership without crossing an unrelated enclosing call."""
        for parent in reversed(self.parents[:-1]):
            if isinstance(parent, ast.Call):

                # Known expression constructors establish SQL ownership directly.
                if self.qualified(parent.func) in query_types.EXPRESSION_FUNCTIONS:
                    return True

                # Stop at the first enclosing call, even when it is not a SQL API.
                return (
                    isinstance(parent.func, ast.Attribute)
                    and parent.func.attr in {"where", "filter", "having"}
                    and self.kind(parent.func.value) in {"@statement", "@single_statement"}
                )
        return False

    def visit_Call(self, node: ast.Call) -> None:
        """Check copies, SQL expression inputs, scalar APIs, and size-only loads."""
        parent = self.parents[-2] if len(self.parents) > 1 else None
        if self.is_copy(node) and self.accepts_sequence(parent):
            self.findings.append(Finding.at(node, "SLOP006", "avoid list() around query-result rows when a sequence is sufficient"))

        # Unrelated objects may also define in_; require expression provenance.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "in_"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.ListComp)
            and not node.keywords
            and (self.kind(node.func.value) == "@expression" or self.in_expression_context())
        ):
            self.findings.append(Finding.at(node.args[0], "SLOP008", "pass a generator expression directly to SQLAlchemy in_()"))

        # Scalar APIs still need the original cardinality and null-handling consumer.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "scalars"
            and self.kind(node.func.value) in query_types.EXECUTE_RESULTS
        ):
            self.findings.append(Finding.at(node, "SLOP018", SCALAR_API_MESSAGE))
        self.findings.extend(self.size_only_load(node, parent))
        self.generic_visit(node)

    def size_use(self, node: ast.AST, parent: ast.AST | None) -> bool:
        """Recognize length consumers and direct truth tests."""
        if isinstance(parent, ast.Call):
            return self.qualified(parent.func) in {"len", "bool"} and parent.args == [node] and not parent.keywords
        if isinstance(parent, (ast.If, ast.While, ast.IfExp)):
            return parent.test is node
        return isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not)

    def size_only_load(self, node: ast.Call, parent: ast.AST | None) -> list[Finding]:
        """Preserve rows rebound or consumed as data rather than only their size."""
        if self.kind(node) != "@rows" or parent is None:
            return []
        candidate = self.size_use(node, parent)
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) and self.functions:
            name = parent.targets[0].id
            function = self.functions[-1]

            # Closure reads count as data reuse even outside this statement block.
            uses = name_loads(function, name)
            stores = [
                child
                for child in scope_nodes(function)
                if isinstance(child, ast.Name) and child.id == name and isinstance(child.ctx, ast.Store)
            ]
            candidate = len(stores) == 1 and bool(uses) and all(self.size_use(child, owner) for child, owner in uses)

        # Size-only use does not authorize changing locks or transaction semantics.
        if candidate:
            return [
                Finding.at(
                    node, "SLOP019", "review an existence or bounded query instead of loading rows solely for size/truth; preserve locking"
                )
            ]
        return []

    def visit_Expr(self, node: ast.Expr) -> None:
        """Review adjacent same-session commit/refresh calls without rewriting."""
        refresh = called_method(node)
        if refresh and refresh.attr == "refresh" and self.kind(refresh.value) == "@session":

            # Only an immediately preceding same-session commit establishes this candidate.
            for statements, index in statement_positions(self.parents[-2], node):
                commit = called_method(statements[index - 1]) if index else None
                if commit and commit.attr == "commit" and ast.dump(commit.value) == ast.dump(refresh.value):
                    self.findings.append(Finding.at(node, "SLOP022", REFRESH_MESSAGE))
        self.generic_visit(node)


def called_method(statement: ast.AST) -> ast.Attribute | None:
    """Return a synchronous or awaited statement's called method."""
    if not isinstance(statement, ast.Expr):
        return None
    value = statement.value
    if isinstance(value, ast.Await):
        value = value.value
    return value.func if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) else None


def analyze_queries(tree: ast.AST) -> list[Finding]:
    """Analyze a parsed file with fresh database provenance."""
    analyzer = QueryAnalyzer()
    analyzer.visit(tree)
    return analyzer.findings
