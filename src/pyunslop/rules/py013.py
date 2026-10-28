from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY013"
MESSAGE = "do not import retired src.errors wrappers; use FastAPI HTTPException directly"


def check(node: ast.Import | ast.ImportFrom, context: AnalysisVisitor) -> None:
    """Reject known absolute import forms of the retired exception wrappers."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "src.errors" or alias.name.startswith("src.errors."):
                context.findings.append((alias, CODE, MESSAGE))

    # Relative imports are intentionally left unresolved rather than guessed.
    elif not node.level and (
        node.module == "src.errors"
        or (node.module or "").startswith("src.errors.")
        or (node.module == "src" and any(alias.name == "errors" for alias in node.names))
    ):
        context.findings.append((node, CODE, MESSAGE))
