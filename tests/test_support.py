import ast
from pyunslop.source import Source
from pyunslop.analysis import check_patterns as analyze
from pyunslop.diagnostics import Finding


def check_patterns(tree: ast.Module, source: str = "") -> list[Finding]:
    """Run AST-focused fixtures without requiring their original source text."""
    return analyze(Source(source, tree))
