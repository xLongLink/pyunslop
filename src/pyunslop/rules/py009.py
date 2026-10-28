from __future__ import annotations

import ast
from ..api import is_raw_response
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import FunctionNode, QualifiedName

CODE = "PY009"
BODYLESS_STATUS_NAMES = {"CONTINUE", "SWITCHING_PROTOCOLS", "PROCESSING", "EARLY_HINTS", "NO_CONTENT", "RESET_CONTENT", "NOT_MODIFIED"}


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
    if is_raw_response(response_class) and response_class.rsplit(".", 1)[-1] not in {"JSONResponse", "ORJSONResponse", "UJSONResponse"}:
        return False

    # api_route can describe a HEAD-only endpoint without a .head decorator.
    methods = values.get("methods")
    if isinstance(methods, (ast.List, ast.Tuple, ast.Set)) and methods.elts:
        return not all(
            isinstance(method, ast.Constant) and isinstance(method.value, str) and method.value.upper() == "HEAD" for method in methods.elts
        )
    return True


def check(node: FunctionNode, context: AnalysisVisitor) -> None:
    """Require explicit JSON response schemas after analyzing endpoint returns."""
    returns = context.raw_returns[id(node)]
    if context.annotation_kind(node.returns) == "@response" or (returns and all(returns)):
        return
    for route in context.routes[id(node)]:
        if needs_response_model(route, context.qualified):
            context.findings.append((route, CODE, "declare response_model explicitly for this JSON endpoint"))
