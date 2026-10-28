from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY006"
DOMAIN_CLASSES = {"Postgres", "Kubernetes"}


def check(node: ast.Call, context: AnalysisVisitor) -> None:
    """Require named instances only for explicitly allowlisted domain classes."""
    if not isinstance(node.func, ast.Attribute):
        return
    owner = node.func.value

    # Follow property access such as applications.logs back to the constructor.
    while isinstance(owner, ast.Attribute):
        owner = owner.value
    if isinstance(owner, ast.Call):
        name = context.qualified(owner.func).rsplit(".", 1)[-1]
        if name in DOMAIN_CLASSES:
            context.findings.append((owner, CODE, f"assign the {name} instance to a name before calling its methods"))
