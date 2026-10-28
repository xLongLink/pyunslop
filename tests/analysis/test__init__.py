import ast
import textwrap
from tests.support import codes
from pyunslop.analysis.queries import analyze_queries
from pyunslop.analysis.endpoints import analyze_endpoints


def test_domains_are_independent_on_the_same_tree() -> None:
    """Running endpoint and query checks in either order yields the same results."""
    source = textwrap.dedent("""\
        from fastapi import APIRouter
        from sqlalchemy.ext.asyncio import AsyncSession
        router = APIRouter()
        @router.get('/')
        async def fetch(session: AsyncSession):
            return (await session.execute(stmt)).all()
        """)
    tree = ast.parse(source)
    queries = analyze_queries(tree)
    endpoints = analyze_endpoints(tree)
    assert [finding.code for finding in queries] == ["PY001"]
    assert [finding.code for finding in endpoints] == ["PY009"]

    # Reversing the order must not expose another analyzer's state.
    assert analyze_endpoints(tree) == endpoints
    assert analyze_queries(tree) == queries

    # Analyzers share the input tree but may not rewrite it.
    assert ast.dump(tree) == ast.dump(ast.parse(source))


def test_policies_are_always_enabled() -> None:
    """Enable both repository policies without requiring configuration."""
    source = '"""Module docs."""\nfrom src.errors import ConflictError\n'
    assert sorted(codes(source)) == ["PY013", "PY014"]
