from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from pyunslop.diagnostics import Finding
from collections.abc import Sequence

if TYPE_CHECKING:
    from pyunslop.source import Source
    from pyunslop.contracts import ComprehensionNode

CODE = "SLOP017"


def argument_dependencies(arguments: Sequence[ast.expr]) -> list[ast.NamedExpr]:
    """Find bindings reused by a later constructor argument."""
    findings: list[ast.NamedExpr] = []
    for index, argument in enumerate(arguments):
        bindings = [node for node in ast.walk(argument) if isinstance(node, ast.NamedExpr)]
        later = [node for value in arguments[index + 1 :] for node in ast.walk(value)]

        # Only later arguments can consume the newly assigned constructor value.
        findings.extend(
            binding
            for binding in bindings
            if any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == binding.target.id for node in later)
        )
    return findings


def comprehension_dependencies(node: ComprehensionNode) -> list[ast.NamedExpr]:
    """Inspect constructor calls inside comprehension output expressions."""
    roots = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
    findings = []
    for root in roots:

        # Constructor naming is deliberately conservative; ordinary calls are ignored.
        for call in (item for item in ast.walk(root) if isinstance(item, ast.Call)):
            name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
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
