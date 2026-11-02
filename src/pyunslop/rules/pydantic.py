from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding
from pyunslop.analysis.bindings import BindingVisitor

if TYPE_CHECKING:
    from pyunslop.source import Source

CODE = "SLOP014"
MODEL_BASES = {"pydantic.BaseModel", "pydantic.main.BaseModel", "pydantic.v1.BaseModel", "pydantic.v1.main.BaseModel"}
MESSAGE = "order model fields from shortest name to longest within each section; review validation dependencies before reordering"


class ModelAnalyzer(BindingVisitor):
    """Resolve directly imported model bases at each class definition."""

    def __init__(self, source: Source) -> None:
        """Retain source section boundaries alongside name bindings."""
        super().__init__()
        self.source_lines = source.lines
        self.findings: list[Finding] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Review fields before class-local bindings shadow module imports."""
        if any(self.annotation(base) in MODEL_BASES for base in node.bases):
            previous: tuple[ast.AnnAssign, str] | None = None
            for statement in node.body:
                # Only annotated names can be model fields.
                if (
                    not isinstance(statement, ast.AnnAssign)
                    or not isinstance(statement.target, ast.Name)
                    # Pydantic excludes private state and class-level configuration.
                    or statement.target.id.startswith("_")
                    or statement.target.id == "model_config"
                    or self.annotation(statement.annotation) in {"typing.ClassVar", "typing_extensions.ClassVar"}
                ):
                    previous = None
                    continue

                # Compare adjacent eligible fields, including after a section boundary.
                name = statement.target.id
                if previous is not None:
                    previous_statement, previous_name = previous

                    # Only gaps between declarations divide sections, not multiline defaults.
                    gap = self.source_lines[previous_statement.end_lineno : statement.lineno - 1]
                    if not any(not line.strip() for line in gap) and len(name) < len(previous_name):
                        self.findings.append(Finding.at(statement.target, CODE, MESSAGE))
                previous = statement, name
        super().visit_ClassDef(node)


def check_pydantic(source: Source) -> list[Finding]:
    """Review field order without inferring custom model inheritance."""
    analyzer = ModelAnalyzer(source)
    analyzer.visit(source.tree)
    return analyzer.findings
