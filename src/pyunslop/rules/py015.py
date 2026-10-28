from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
    from ..contracts import FunctionNode, QualifiedName

CODE = "PY015"


def single_literal_case(decorator: ast.expr, qualified: QualifiedName) -> bool:
    """Preserve dynamic cases and explicit fixture or collection behavior."""
    if not isinstance(decorator, ast.Call) or qualified(decorator.func) != "pytest.mark.parametrize":
        return False
    options = {keyword.arg: keyword.value for keyword in decorator.keywords}
    if any(key in options for key in (None, "ids", "scope")):
        return False
    indirect = options.get("indirect")
    if indirect is not None and not (isinstance(indirect, ast.Constant) and indirect.value is False):
        return False

    # pytest.param and computed cases can carry marks or collection semantics.
    values = decorator.args[1] if len(decorator.args) > 1 else options.get("argvalues")
    if not isinstance(values, (ast.List, ast.Tuple)) or len(values.elts) != 1:
        return False
    try:
        ast.literal_eval(values.elts[0])
    except (ValueError, TypeError):
        return False
    return True


class Rule:
    """Keep collection-hook exemptions local to parametrization checks."""

    def __init__(self) -> None:
        """Start without module collection hooks."""
        self.collection_hooks = False

    def check_module(self, node: ast.Module, _context: AnalysisVisitor) -> None:
        """Collect hooks before checking any test decorators."""
        self.collection_hooks = any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name in {"pytest_generate_tests", "pytest_collection_modifyitems"}
            for item in node.body
        )

    def check(self, node: FunctionNode, context: AnalysisVisitor) -> None:
        """Review single-case parametrization without fixture or collection behavior."""
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if not self.collection_hooks and not any(argument.arg == "request" for argument in args):
            for decorator in node.decorator_list:
                if single_literal_case(decorator, context.qualified):
                    context.findings.append((decorator, CODE, "replace single literal-case parametrization with a direct test"))
