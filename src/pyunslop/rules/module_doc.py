from __future__ import annotations

import re
import ast
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding
from pyunslop.analysis.bindings import BindingVisitor

if TYPE_CHECKING:
    from pyunslop.source import Source
    from pyunslop.contracts import QualifiedName

CODE = "SLOP012"
CLI_HELP_APIS = {"argparse.ArgumentParser", "click.command", "click.group", "typer.Typer"}
ALEMBIC_HEADER = re.compile(
    r"^Revision ID:[ \t]+\S+[ \t]*\n"
    r"Revises:[^\n]*\n"
    r"Create Date:[ \t]+\d{4}-\d{2}-\d{2}[ \t]+\d{2}:\d{2}:\d{2}(?:\.\d+)?[ \t]*$",
    re.MULTILINE,
)


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

    def visit_Call(self, node: ast.Call) -> None:
        """Record help uses while import aliases are in scope."""
        self.cli_doc_used |= uses_cli_doc(node, self.qualified)
        self.generic_visit(node)


def check_module_doc(source: Source) -> list[Finding]:
    """Allow Alembic revision headers and documentation consumed by CLI help."""
    doc = ast.get_docstring(source.tree)
    if doc is None or ALEMBIC_HEADER.search(doc):
        return []
    analyzer = ModuleDocAnalyzer()
    analyzer.visit(source.tree)

    # Merely referencing __doc__ does not establish a CLI-help exemption.
    if analyzer.cli_doc_used:
        return []
    return [Finding.at(source.tree.body[0], CODE, "repository policy forbids leading module docstrings")]
