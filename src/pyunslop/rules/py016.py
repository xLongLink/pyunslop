from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY016"
MESSAGE = "use pytest instead of unittest"


def check(node: ast.Import | ast.ImportFrom, context: AnalysisVisitor) -> None:
    """Flag absolute unittest imports, including aliases and submodules."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "unittest" or alias.name.startswith("unittest."):
                context.findings.append((alias, CODE, MESSAGE))
    elif not node.level and (node.module == "unittest" or (node.module or "").startswith("unittest.")):
        context.findings.append((node, CODE, MESSAGE))
