from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding
from pyunslop.analysis.bindings import BindingVisitor

if TYPE_CHECKING:
    from pyunslop.source import Source

CODE = "SLOP017"
MODEL_BASES = {"pydantic.BaseModel", "pydantic.main.BaseModel", "pydantic.v1.BaseModel", "pydantic.v1.main.BaseModel"}
MESSAGE = "order model fields from shortest name to longest within each section; review validation dependencies before reordering"


def is_field(statement: ast.stmt, context: BindingVisitor) -> bool:
    """Exclude Pydantic private attributes and class-level configuration."""
    return (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and not statement.target.id.startswith("_")
        and statement.target.id != "model_config"
        and context.annotation(statement.annotation) not in {"typing.ClassVar", "typing_extensions.ClassVar"}
    )


def check_fields(node: ast.ClassDef, context: BindingVisitor) -> list[Finding]:
    """Review field-name lengths within directly recognized Pydantic models."""
    if not any(context.annotation(base) in MODEL_BASES for base in node.bases):
        return []
    findings = []
    previous: ast.AnnAssign | None = None
    for statement in node.body:

        # Methods, private state, and configuration terminate a field run.
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name) or not is_field(statement, context):
            previous = None
            continue

        # Field defaults may span lines; only gaps between declarations divide sections.
        if previous is not None and isinstance(previous.target, ast.Name):
            gap = context.source_lines[previous.end_lineno : statement.lineno - 1]
            if not any(not line.strip() for line in gap) and len(statement.target.id) < len(previous.target.id):
                findings.append(Finding.at(statement.target, CODE, MESSAGE))

        # Compare adjacent fields, including after a section boundary.
        previous = statement
    return findings


class ModelAnalyzer(BindingVisitor):
    """Resolve directly imported model bases at each class definition."""

    def __init__(self, source: Source) -> None:
        """Retain source section boundaries alongside name bindings."""
        super().__init__(source.text)
        self.findings: list[Finding] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Review fields before class-local bindings shadow module imports."""
        self.findings.extend(check_fields(node, self))
        super().visit_ClassDef(node)


def check_pydantic(source: Source) -> list[Finding]:
    """Review field order without inferring custom model inheritance."""
    analyzer = ModelAnalyzer(source)
    analyzer.visit(source.tree)
    return analyzer.findings
