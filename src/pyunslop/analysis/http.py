from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts import QualifiedName

ROUTER_TYPES = {"fastapi.FastAPI", "fastapi.applications.FastAPI", "fastapi.APIRouter", "fastapi.routing.APIRouter"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route"}
BODYLESS_STATUS_NAMES = {"CONTINUE", "SWITCHING_PROTOCOLS", "PROCESSING", "EARLY_HINTS", "NO_CONTENT", "RESET_CONTENT", "NOT_MODIFIED"}
RAW_RESPONSE_NAMES = {
    "Response",
    "StreamingResponse",
    "RedirectResponse",
    "FileResponse",
    # Text and JSON response objects also bypass response-model serialization.
    "PlainTextResponse",
    "HTMLResponse",
    "JSONResponse",
    "ORJSONResponse",
    "UJSONResponse",
}


def annotation_kind(name: str) -> str:
    """Recognize response types that bypass FastAPI response serialization."""
    module, _, symbol = name.rpartition(".")
    return "@response" if module in {"fastapi", "fastapi.responses", "starlette.responses"} and symbol in RAW_RESPONSE_NAMES else ""


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


def is_external(route: ast.Call) -> bool:
    """Recognize an explicit external-protocol contract."""
    values = {keyword.arg: keyword.value for keyword in route.keywords}
    extra = values.get("openapi_extra")
    if isinstance(extra, ast.Dict):
        return any(
            isinstance(key, ast.Constant) and key.value == "x-external-protocol" and isinstance(value, ast.Constant) and value.value is True
            for key, value in zip(extra.keys, extra.values)
        )
    return False


def is_success_envelope(node: ast.AST | None, qualified: QualifiedName) -> bool:
    """Identify literal success envelopes without guessing dynamic payload shapes."""
    if isinstance(node, ast.Dict):
        fields: dict[str | None, ast.expr] = {
            key.value: value for key, value in zip(node.keys, node.values) if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    elif isinstance(node, ast.Call) and qualified(node.func) == "dict" and not node.args:
        fields = {keyword.arg: keyword.value for keyword in node.keywords}
    else:
        return False

    # A success flag alone is not an envelope unless it wraps detail or data.
    success = fields.get("success")
    return isinstance(success, ast.Constant) and success.value is True and bool({"detail", "data"} & fields.keys())
