ROUTER_TYPES = {"fastapi.FastAPI", "fastapi.applications.FastAPI", "fastapi.APIRouter", "fastapi.routing.APIRouter"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route"}

# These response types bypass FastAPI's ordinary model serialization.
RAW_RESPONSE_NAMES = {
    "Response",
    "StreamingResponse",
    "RedirectResponse",
    "FileResponse",
    "PlainTextResponse",
    "HTMLResponse",
    # Direct JSONResponse instances are raw even though the default JSON class is not an exemption.
    "JSONResponse",
    "ORJSONResponse",
    "UJSONResponse",
}


def is_raw_response(name: str) -> bool:
    """Recognize response types that bypass FastAPI response serialization."""
    module, _, symbol = name.rpartition(".")
    return module in {"fastapi", "fastapi.responses", "starlette.responses"} and symbol in RAW_RESPONSE_NAMES
