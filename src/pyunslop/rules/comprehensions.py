from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from collections.abc import Sequence
from pyunslop.diagnostics import Finding

if TYPE_CHECKING:
    from pyunslop.source import Source
    from pyunslop.contracts import ComprehensionNode

CODE = "SLOP016"


def argument_dependencies(arguments: Sequence[ast.expr]) -> list[ast.NamedExpr]:
    """Find bindings reused by a later constructor argument."""
    groups: list[list[ast.NamedExpr]] = []
    later_names: set[str] = set()
    for argument in reversed(arguments):
        nodes = list(ast.walk(argument))
        bindings = [node for node in nodes if isinstance(node, ast.NamedExpr)]
        names = {node.id for node in nodes if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}

        # Same-argument reads must not count as later-argument dependencies.
        groups.append([binding for binding in bindings if binding.target.id in later_names])
        later_names.update(names)
    return [binding for group in reversed(groups) for binding in group]


def comprehension_dependencies(node: ComprehensionNode) -> list[ast.NamedExpr]:
    """Inspect constructor calls inside comprehension output expressions."""
    roots = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
    findings = []

    # Constructor naming is deliberately conservative; ordinary calls are ignored.
    for root in roots:
        for call in (item for item in ast.walk(root) if isinstance(item, ast.Call)):
            name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")

            # Leading underscores do not change constructor recognition.
            if not name.lstrip("_")[:1].isupper():
                continue

            # Positional and keyword values are evaluated in this order.
            arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
            findings.extend(argument_dependencies(arguments))
    return findings


def check_comprehensions(source: Source) -> list[Finding]:
    """Report each dependent binding once, including nested comprehensions."""
    reported: set[ast.NamedExpr] = set()
    findings = []
    for node in ast.walk(source.tree):
        if not isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue

        # The same nested binding can be reached from multiple comprehension roots.
        for binding in comprehension_dependencies(node):
            if binding not in reported:
                reported.add(binding)

                # Nested comprehensions can expose the same binding more than once.
                findings.append(
                    Finding.at(
                        binding, CODE, "use an explicit loop when a comprehension's constructor arguments depend on a walrus binding"
                    )
                )
    return findings
