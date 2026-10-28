from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analysis import AnalysisVisitor

CODE = "PY003"


def is_copy(node: ast.AST | None, context: AnalysisVisitor) -> bool:
    """Recognize a built-in list conversion around known query rows."""
    return (
        isinstance(node, ast.Call)
        and context.qualified(node.func) == "list"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], ast.Call)
        and context.kind(node.args[0]) == "@rows"
    )


def accepts_sequence(parent: ast.AST | None, context: AnalysisVisitor) -> bool:
    """Keep copies required by explicit mutable or unknown contracts."""
    if isinstance(parent, ast.Assign):
        return all(
            isinstance(target, ast.Name) and context.contracts.get(target.id, "") in {"", "typing.Sequence", "collections.abc.Sequence"}
            for target in parent.targets
        )
    if isinstance(parent, ast.AnnAssign):
        return context.annotation(parent.annotation) in {"typing.Sequence", "collections.abc.Sequence"}

    # Unknown return types and consumers may require actual mutable lists.
    if isinstance(parent, ast.Return) and context.functions:
        return context.annotation(context.functions[-1].returns) in {"typing.Sequence", "collections.abc.Sequence"}
    return False


def check(node: ast.Call, context: AnalysisVisitor) -> None:
    """Report redundant query-row copies in sequence-compatible contexts."""
    parent = context.parents[-2] if len(context.parents) > 1 else None
    if is_copy(node, context) and accepts_sequence(parent, context):
        context.findings.append((node, CODE, "avoid list() around query-result rows when a sequence is sufficient"))
