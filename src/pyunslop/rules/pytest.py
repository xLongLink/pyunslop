from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding
from pyunslop.analysis.bindings import BindingVisitor

if TYPE_CHECKING:
    from pyunslop.source import Source
    from pyunslop.contracts import FunctionNode, QualifiedName

CODE = "SLOP014"


def single_literal_case(decorator: ast.expr, qualified: QualifiedName) -> bool:
    """Preserve dynamic cases and explicit fixture or collection behavior."""
    if not isinstance(decorator, ast.Call) or qualified(decorator.func) != "pytest.mark.parametrize":
        return False
    options = {keyword.arg: keyword.value for keyword in decorator.keywords}
    if any(key in options for key in (None, "ids", "scope")):
        return False

    # Even a single indirect case may control fixture setup and collection.
    indirect = options.get("indirect")
    if indirect is not None and not (isinstance(indirect, ast.Constant) and indirect.value is False):
        return False

    # pytest.param and computed cases can carry marks or collection semantics.
    values = decorator.args[1] if len(decorator.args) > 1 else options.get("argvalues")
    if not isinstance(values, (ast.List, ast.Tuple)) or len(values.elts) != 1:
        return False

    # Literal evaluation rejects computed cases without executing inspected code.
    try:
        ast.literal_eval(values.elts[0])
    except (ValueError, TypeError):
        return False
    return True


class ParametrizationAnalyzer(BindingVisitor):
    """Keep collection-hook exemptions local to parametrization checks."""

    def __init__(self, source: Source) -> None:
        """Collect module hooks before resolving test decorators."""
        super().__init__()
        self.findings: list[Finding] = []
        self.collection_hooks = any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name in {"pytest_generate_tests", "pytest_collection_modifyitems"}
            for item in source.tree.body
        )

    def visit_FunctionDef(self, node: FunctionNode) -> None:
        """Review single-case parametrization without fixture or collection behavior."""
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if not self.collection_hooks and not any(argument.arg == "request" for argument in args):
            for decorator in node.decorator_list:

                # Preserve decorators whose case carries fixture or collection semantics.
                if single_literal_case(decorator, self.qualified):
                    self.findings.append(Finding.at(decorator, CODE, "replace single literal-case parametrization with a direct test"))
        super().visit_FunctionDef(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def check_pytest(source: Source) -> list[Finding]:
    """Review parametrization with fresh per-file collection state."""
    analyzer = ParametrizationAnalyzer(source)
    analyzer.visit(source.tree)
    return analyzer.findings
