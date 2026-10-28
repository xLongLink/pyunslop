import ast
import pytest
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
    assert [finding.code for finding in queries] == ["SLOP004"]
    assert [finding.code for finding in endpoints] == ["SLOP010"]

    # Reversing the order must not expose another analyzer's state.
    assert analyze_endpoints(tree) == endpoints
    assert analyze_queries(tree) == queries

    # Analyzers share the input tree but may not rewrite it.
    assert ast.dump(tree) == ast.dump(ast.parse(source))


def test_policies_are_always_enabled() -> None:
    """Enable the module-docstring policy without requiring configuration."""
    assert codes('"""Module docs."""\n') == ["SLOP012"]


@pytest.mark.parametrize(
    "source",
    [
        "import unittest",
        "import unittest as ut",
        "import unittest.mock as mock",
        "from unittest import TestCase as Case",
        "from unittest.mock import patch, Mock",
        "from unittest import *",
        "def test_example():\n    import unittest",
        "from src.errors import ConflictError",
        "import src.errors as errors",
        "from src import errors",
        "import src.errors.http",
        "from src.errors.http import ConflictError",
    ],
)
def test_imports_do_not_enforce_project_design_choices(source: str) -> None:
    """Allow imports previously rejected by project-specific policies."""
    assert codes(source) == []
