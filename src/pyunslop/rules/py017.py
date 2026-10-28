from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY017"
MODEL_BASES = {"pydantic.BaseModel", "pydantic.main.BaseModel", "pydantic.v1.BaseModel", "pydantic.v1.main.BaseModel"}
MESSAGE = "order model fields from shortest name to longest within each section; review validation dependencies before reordering"


def is_field(statement: ast.stmt, context: AnalysisVisitor) -> bool:
    """Exclude Pydantic private attributes and class-level configuration."""
    return (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and not statement.target.id.startswith("_")
        and statement.target.id != "model_config"
        and context.annotation(statement.annotation) not in {"typing.ClassVar", "typing_extensions.ClassVar"}
    )


def check(node: ast.ClassDef, context: AnalysisVisitor) -> None:
    """Review field-name lengths within directly recognized Pydantic models."""
    if not any(context.annotation(base) in MODEL_BASES for base in node.bases):
        return
    previous: ast.AnnAssign | None = None
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name) or not is_field(statement, context):
            previous = None
            continue

        # Field defaults may span lines; only gaps between declarations divide sections.
        if previous is not None and isinstance(previous.target, ast.Name):
            gap = context.source_lines[previous.end_lineno : statement.lineno - 1]
            if not any(not line.strip() for line in gap) and len(statement.target.id) < len(previous.target.id):
                context.findings.append((statement.target, CODE, MESSAGE))
        previous = statement
