import ast

ROUTER_TYPES = {"fastapi.FastAPI", "fastapi.applications.FastAPI", "fastapi.APIRouter", "fastapi.routing.APIRouter"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route"}
RAW_RESPONSE_NAMES = {
    "Response", "StreamingResponse", "RedirectResponse", "FileResponse",
    "PlainTextResponse", "HTMLResponse", "JSONResponse", "ORJSONResponse", "UJSONResponse",
}


def is_raw_response(name):
    module, _, symbol = name.rpartition(".")
    return module in {"fastapi", "fastapi.responses", "starlette.responses"} and symbol in RAW_RESPONSE_NAMES


def options(route):
    return {keyword.arg: keyword.value for keyword in route.keywords}


def is_external(route):
    values = options(route)
    extra = values.get("openapi_extra")
    if isinstance(extra, ast.Dict):
        return any(
            isinstance(key, ast.Constant) and key.value == "x-external-protocol"
            and isinstance(value, ast.Constant) and value.value is True
            for key, value in zip(extra.keys, extra.values)
        )
    return False


def is_bodyless_status(node, qualified):
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return 100 <= node.value < 200 or node.value in {204, 205, 304}
    name = qualified(node)
    if name.startswith(("fastapi.status.HTTP_", "starlette.status.HTTP_")):
        code = name.rsplit(".", 1)[-1].split("_")[1]
        return code.isdigit() and (100 <= int(code) < 200 or int(code) in {204, 205, 304})

    # HTTPStatus enum members are attributes in the AST, not integer constants.
    if name.startswith("http.HTTPStatus."):
        return name.rsplit(".", 1)[-1] in {
            "CONTINUE", "SWITCHING_PROTOCOLS", "PROCESSING", "EARLY_HINTS",
            "NO_CONTENT", "RESET_CONTENT", "NOT_MODIFIED",
        }
    return False


def needs_response_model(route, qualified):
    values = options(route)
    if "response_model" in values or None in values:
        return False
    if route.func.attr == "head" or is_bodyless_status(values.get("status_code"), qualified):
        return False

    # JSONResponse is FastAPI's default; choosing it does not declare a schema.
    response_class = qualified(values.get("response_class"))
    if is_raw_response(response_class) and response_class.rsplit(".", 1)[-1] not in {
        "JSONResponse", "ORJSONResponse", "UJSONResponse",
    }:
        return False

    # api_route can register HEAD-only routes without a .head decorator.
    methods = values.get("methods")
    if isinstance(methods, (ast.List, ast.Tuple, ast.Set)) and methods.elts:
        return not all(
            isinstance(method, ast.Constant) and isinstance(method.value, str)
            and method.value.upper() == "HEAD" for method in methods.elts
        )
    return True


def is_success_envelope(node, qualified):
    if isinstance(node, ast.Dict):
        fields = {
            key.value: value for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    elif isinstance(node, ast.Call) and qualified(node.func) == "dict" and not node.args:
        fields = {keyword.arg: keyword.value for keyword in node.keywords}
    else:
        return False

    # Only a literal success flag plus envelope fields identifies this pattern.
    success = fields.get("success")
    return isinstance(success, ast.Constant) and success.value is True and bool({"detail", "data"} & fields.keys())
