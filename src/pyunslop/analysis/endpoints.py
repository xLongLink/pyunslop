import ast
from dataclasses import dataclass
from pyunslop.analysis import http
from pyunslop.contracts import FunctionNode
from pyunslop.diagnostics import Finding
from pyunslop.analysis.bindings import BindingVisitor


@dataclass
class Endpoint:
    """Keep route contracts and return summaries together for one function."""

    check_returns: bool
    response_models: set[str]
    saw_return: bool = False
    all_returns_raw: bool = True


class EndpointAnalyzer(BindingVisitor):
    """Own FastAPI route recognition, response provenance, and diagnostics."""

    def __init__(self) -> None:
        """Start with independent endpoint and model state for this file."""
        super().__init__()
        self.findings: list[Finding] = []
        self.endpoints: list[Endpoint] = []
        self.transforming_models: set[str] = set()

    def annotation_kind(self, node: ast.expr | None) -> str:
        """Recognize router and raw-response contracts."""
        name = self.annotation(node)
        return "@router" if name in http.ROUTER_TYPES else http.annotation_kind(name)

    def kind(self, node: ast.AST | None) -> str:
        """Propagate only endpoint-specific values through local bindings."""
        if http.is_success_envelope(node, self.qualified):
            return "@envelope"
        if isinstance(node, ast.Call):
            name = self.qualified(node.func)
            return "@router" if name in http.ROUTER_TYPES else http.annotation_kind(name)
        return super().kind(node)

    def routes_for(self, node: FunctionNode) -> list[ast.Call]:
        """Recognize only HTTP decorators owned by a known FastAPI router."""
        return [
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in http.HTTP_METHODS
            and self.kind(decorator.func.value) == "@router"
        ]

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Resolve decorator contracts before entering parameter-local scope."""
        routes = self.routes_for(node)
        endpoint = Endpoint(
            check_returns=bool(routes) and not any(http.is_external(route) for route in routes),
            response_models={
                self.qualified(keyword.value) for route in routes for keyword in route.keywords if keyword.arg == "response_model"
            },
        )

        # Return checks need this context only while its function is active.
        self.endpoints.append(endpoint)
        try:
            super().visit_FunctionDef(node)
        finally:
            self.endpoints.pop()

        # Decorator options are resolved after restoring the enclosing import scope.
        if self.annotation_kind(node.returns) != "@response" and not (endpoint.saw_return and endpoint.all_returns_raw):
            for route in routes:
                if http.needs_response_model(route, self.qualified):
                    self.findings.append(Finding.at(route, "SLOP010", "declare response_model explicitly for this JSON endpoint"))

    # Async routes share the same context lifetime.
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Preserve visible response-model validators and initialization hooks."""
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
        super().visit_ClassDef(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Keep nested returns separate and review only recognized HTTP routes."""
        if self.endpoints:
            endpoint = self.endpoints[-1]
            endpoint.saw_return = True
            return_kind = self.kind(node.value)
            endpoint.all_returns_raw = endpoint.all_returns_raw and return_kind == "@response"

            # Only route returns participate in response-policy checks.
            if endpoint.check_returns:
                self.findings.extend(self.reconstructed_response(node, endpoint))

                # Disabling a schema alone does not opt out of envelope checks.
                if node.value is not None and return_kind == "@envelope":
                    self.findings.append(
                        Finding.at(node.value, "SLOP011", "return the API payload directly instead of a generic success envelope")
                    )
        self.generic_visit(node)

    def reconstructed_response(self, node: ast.Return, endpoint: Endpoint) -> list[Finding]:
        """Retain explicit validation options, computed inputs, and transformations."""
        value = node.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "model_validate"):
            return []
        if len(value.args) != 1 or value.keywords or not isinstance(value.args[0], (ast.Name, ast.Attribute)):
            return []

        # Imported model transformations cannot be proven absent by this local check.
        model = self.qualified(value.func.value)
        if model and model not in self.transforming_models and endpoint.response_models == {model}:
            return [
                # Validation may still intentionally transform the payload.
                Finding.at(
                    value,
                    "SLOP015",
                    "route already validates this response model; avoid reconstruction unless validation intentionally transforms it",
                )
            ]
        return []


def analyze_endpoints(tree: ast.AST) -> list[Finding]:
    """Analyze a parsed file with fresh route and response state."""
    analyzer = EndpointAnalyzer()
    analyzer.visit(tree)
    return analyzer.findings
