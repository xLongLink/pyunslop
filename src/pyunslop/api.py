from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .analysis import AnalysisVisitor
    from .contracts import FunctionNode

ROUTER_TYPES = {"fastapi.FastAPI", "fastapi.applications.FastAPI", "fastapi.APIRouter", "fastapi.routing.APIRouter"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route"}


def route_decorators(node: FunctionNode, context: AnalysisVisitor) -> list[ast.Call]:
    """Identify HTTP routes shared by schema, envelope, and validation checks."""
    return [
        decorator
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr in HTTP_METHODS
        and context.kind(decorator.func.value) == "@router"
    ]
