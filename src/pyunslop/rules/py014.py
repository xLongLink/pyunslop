from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor
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


class Rule:
    """Track CLI-help uses for one module."""

    def __init__(self) -> None:
        """Start without a recognized CLI-help use."""
        self.cli_doc_used = False

    def check_call(self, node: ast.Call, context: AnalysisVisitor) -> None:
        """Record help uses while import aliases are in scope."""
        self.cli_doc_used |= uses_cli_doc(node, context.qualified)

    def check(self, node: ast.Module, context: AnalysisVisitor) -> None:
        """Reject module documentation unless it supplies recognized CLI help."""
        if ast.get_docstring(node) is not None and not self.cli_doc_used:
            context.findings.append((node.body[0], CODE, "repository policy forbids leading module docstrings"))
