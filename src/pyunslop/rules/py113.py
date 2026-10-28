from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY113"


def called_method(statement: ast.AST) -> ast.Attribute | None:
    """Return the called attribute of a synchronous or awaited method statement."""
    if not isinstance(statement, ast.Expr):
        return None
    value = statement.value
    if isinstance(value, ast.Await):
        value = value.value
    return value.func if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) else None


def check(node: ast.Expr, context: AnalysisVisitor) -> None:
    """Review immediate same-session refreshes without assuming redundancy."""
    refresh = called_method(node)
    if not (refresh and refresh.attr == "refresh" and context.kind(refresh.value) == "@session"):
        return
    parent = context.parents[-2]
    for _, statements in ast.iter_fields(parent):
        if not isinstance(statements, list) or node not in statements:
            continue

        # Only an immediately preceding same-session commit establishes this candidate.
        index = statements.index(node)
        commit = called_method(statements[index - 1]) if index else None
        if commit and commit.attr == "commit" and ast.dump(commit.value) == ast.dump(refresh.value):
            context.findings.append(
                (
                    node,
                    CODE,
                    "review post-commit refresh: check expire_on_commit, server defaults, and required relationships before removing it",
                )
            )
