from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import FunctionNode, QualifiedName

CODE = "PY009"
BODYLESS_STATUS_NAMES = {"CONTINUE", "SWITCHING_PROTOCOLS", "PROCESSING", "EARLY_HINTS", "NO_CONTENT", "RESET_CONTENT", "NOT_MODIFIED"}
RAW_RESPONSE_NAMES = {
    "Response",
    "StreamingResponse",
    "RedirectResponse",
    "FileResponse",
    "PlainTextResponse",
    "HTMLResponse",
    # Direct JSONResponse objects bypass serialization, unlike the default response class.
    "JSONResponse",
    "ORJSONResponse",
    "UJSONResponse",
}


def annotation_kind(name: str) -> str:
    """Recognize response types that bypass FastAPI response serialization."""
    module, _, symbol = name.rpartition(".")
    return "@response" if module in {"fastapi", "fastapi.responses", "starlette.responses"} and symbol in RAW_RESPONSE_NAMES else ""


def kind(node: ast.AST, context: AnalysisVisitor) -> str:
    """Recognize constructed raw responses while their aliases are in scope."""
    return annotation_kind(context.qualified(node.func)) if isinstance(node, ast.Call) else ""


def is_bodyless_status(node: ast.AST | None, qualified: QualifiedName) -> bool:
    """Resolve literal and known symbolic bodyless HTTP statuses."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return 100 <= node.value < 200 or node.value in {204, 205, 304}
    name = qualified(node)
    if name.startswith(("fastapi.status.HTTP_", "starlette.status.HTTP_")):
        code = name.rsplit(".", 1)[-1].split("_")[1]
        return code.isdigit() and (100 <= int(code) < 200 or int(code) in {204, 205, 304})

    # Standard-library HTTPStatus members also encode intentional bodyless responses.
    if name.startswith("http.HTTPStatus."):
        return name.rsplit(".", 1)[-1] in BODYLESS_STATUS_NAMES
    return False


def needs_response_model(route: ast.Call, qualified: QualifiedName) -> bool:
    """Exempt explicit contracts, bodyless routes, and raw response classes."""
    values = {keyword.arg: keyword.value for keyword in route.keywords}
    if "response_model" in values or None in values:
        return False
    if (isinstance(route.func, ast.Attribute) and route.func.attr == "head") or is_bodyless_status(values.get("status_code"), qualified):
        return False

    # Selecting FastAPI's JSON default does not itself declare a schema.
    response_class = qualified(values.get("response_class"))
    if annotation_kind(response_class) and response_class.rsplit(".", 1)[-1] not in {"JSONResponse", "ORJSONResponse", "UJSONResponse"}:
        return False

    # api_route can describe a HEAD-only endpoint without a .head decorator.
    methods = values.get("methods")
    if isinstance(methods, (ast.List, ast.Tuple, ast.Set)) and methods.elts:
        return not all(
            isinstance(method, ast.Constant) and isinstance(method.value, str) and method.value.upper() == "HEAD" for method in methods.elts
        )
    return True


class Rule:
    """Collect raw-return exemptions independently for each endpoint."""

    def __init__(self) -> None:
        """Start without return provenance for this file."""
        self.raw_returns: dict[int, list[bool]] = {}

    def check_function(self, node: FunctionNode, _context: AnalysisVisitor) -> None:
        """Initialize return tracking before entering a function body."""
        self.raw_returns[id(node)] = []

    def check_return(self, node: ast.Return, context: AnalysisVisitor) -> None:
        """Keep nested functions' returns separate from their enclosing endpoint."""
        if context.functions:
            self.raw_returns[id(context.functions[-1])].append(context.kind(node.value) == "@response")

    def check(self, node: FunctionNode, context: AnalysisVisitor) -> None:
        """Require explicit JSON response schemas after analyzing endpoint returns."""
        returns = self.raw_returns[id(node)]
        if context.annotation_kind(node.returns) == "@response" or (returns and all(returns)):
            return
        for route in context.routes[id(node)]:
            if needs_response_model(route, context.qualified):
                context.findings.append((route, CODE, "declare response_model explicitly for this JSON endpoint"))
