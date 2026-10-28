import ast
import textwrap
from pyunslop.source import Source
from pyunslop.analysis import check_patterns as analyze
from pyunslop.diagnostics import Finding

QUERY_IMPORTS = "from sqlalchemy.ext.asyncio import AsyncSession\nfrom collections.abc import Sequence\n"


def check_patterns(tree: ast.Module, source: str = "") -> list[Finding]:
    """Run AST-focused fixtures without requiring their original source text."""
    return analyze(Source(source, tree))


def codes(source: str) -> list[str]:
    """Return native warning codes for a dedented source fixture."""
    return [finding.code for finding in check_patterns(ast.parse(textwrap.dedent(source)))]


def query_codes(source: str) -> list[str]:
    """Resolve query fixtures with shared SQLAlchemy and Sequence imports."""
    return codes(QUERY_IMPORTS + textwrap.dedent(source))
