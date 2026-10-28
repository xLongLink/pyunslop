from __future__ import annotations

import ast
from .py010 import is_external
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import FunctionNode

CODE = "PY101"
MESSAGE = "route already validates this response model; avoid reconstruction unless validation intentionally transforms it"


class Rule:
    """Own response-model contracts and visible transformation exemptions."""

    def __init__(self) -> None:
        """Start with no model contracts or transformations for this file."""
        self.response_models: dict[int, set[str]] = {}
        self.transforming_models: set[str] = set()

    def check_function(self, node: FunctionNode, context: AnalysisVisitor) -> None:
        """Resolve decorator model aliases before parameter names can shadow them."""
        self.response_models[id(node)] = {
            context.qualified(keyword.value)
            for route in context.routes[id(node)]
            for keyword in route.keywords
            if keyword.arg == "response_model"
        }

    def check_class(self, node: ast.ClassDef, context: AnalysisVisitor) -> None:
        """Record visible validators and custom initialization hooks."""
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = [decorator.func if isinstance(decorator, ast.Call) else decorator for decorator in method.decorator_list]

            # Custom initialization and validators can intentionally transform a response.
            if method.name in {"model_validate", "model_post_init", "__init__"} or any(
                context.qualified(decorator)
                in {"pydantic.field_validator", "pydantic.model_validator", "pydantic.validator", "pydantic.root_validator"}
                for decorator in decorators
            ):
                self.transforming_models.add(node.name)

    def check(self, node: ast.Return, context: AnalysisVisitor) -> None:
        """Review duplicate response validation while preserving visible transformations."""
        if not context.functions:
            return
        function = context.functions[-1]
        routes = context.routes[id(function)]
        if not routes or any(is_external(route) for route in routes):
            return

        # Only a direct model_validate return can duplicate this route contract.
        value = node.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "model_validate"):
            return

        # Explicit options and computed inputs may intentionally transform the result.
        if len(value.args) != 1 or value.keywords or not isinstance(value.args[0], (ast.Name, ast.Attribute)):
            return
        model = context.qualified(value.func.value)
        if model and model not in self.transforming_models and self.response_models[id(function)] == {model}:
            context.findings.append((value, CODE, MESSAGE))
