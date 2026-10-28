from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from ..diagnostics import Finding
from ..analysis.bindings import BindingVisitor

if TYPE_CHECKING:
    from ..source import Source
    from ..contracts import QualifiedName

CODE = "PY014"
CLI_HELP_APIS = {"argparse.ArgumentParser", "click.command", "click.group", "typer.Typer"}


def uses_cli_doc(call: ast.Call, qualified: QualifiedName) -> bool:
    """Exempt module documentation intentionally consumed by known CLI help APIs."""
    return qualified(call.func) in CLI_HELP_APIS and any(
        keyword.arg in {"description", "epilog", "help"}
        and any(isinstance(node, ast.Name) and node.id == "__doc__" for node in ast.walk(keyword.value))
        for keyword in call.keywords
    )


class ModuleDocAnalyzer(BindingVisitor):
    """Track CLI-help uses for one module."""

    def __init__(self) -> None:
        """Start without a recognized CLI-help use."""
        super().__init__()
        self.cli_doc_used = False

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Record help uses while import aliases are in scope."""
        self.cli_doc_used |= uses_cli_doc(node, self.qualified)
        self.generic_visit(node)


def check_module_doc(source: Source) -> list[Finding]:
    """Reject module documentation unless it supplies recognized CLI help."""
    if ast.get_docstring(source.tree) is None:
        return []
    analyzer = ModuleDocAnalyzer()
    analyzer.visit(source.tree)
    if analyzer.cli_doc_used:
        return []
    return [Finding.at(source.tree.body[0], CODE, "repository policy forbids leading module docstrings")]
