import ast
import tempfile
import textwrap
import tokenize
import unittest
from pathlib import Path
from pyunslop import check_file
from unittest import mock
from test_support import check_patterns
from pyunslop.analysis.queries import analyze_queries
from pyunslop.analysis.endpoints import analyze_endpoints


class AnalysisTests(unittest.TestCase):
    """Exercise analyzer boundaries and shared parsing through observable results."""

    def test_one_source_parse_feeds_all_native_rules(self) -> None:
        """Share parsing and tokenization across independent analyzers."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("from src.errors import ConflictError\n#bad\n")
            with (
                mock.patch("pyunslop.source.ast.parse", wraps=ast.parse) as parse,
                mock.patch("pyunslop.source.tokenize.generate_tokens", wraps=tokenize.generate_tokens) as tokens,
            ):
                warnings = check_file(path)

        # Multiple AST traversals must not repeat parsing or tokenization.
        assert parse.call_count == 1
        assert tokens.call_count == 1
        assert {warning.code for warning in warnings} == {"PY013", "CM002", "CM003"}

    def test_analysis_state_is_not_shared_between_files(self) -> None:
        """Keep imported session provenance local to one analyzer invocation."""
        typed = ast.parse(
            "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(s: AsyncSession):\n    return (await s.execute(stmt)).all()\n"
        )
        unknown = ast.parse("async def fetch(s):\n    return (await s.execute(stmt)).all()\n")
        assert [finding.code for finding in check_patterns(typed)] == ["PY001"]
        assert check_patterns(unknown) == []
        assert [finding.code for finding in check_patterns(typed)] == ["PY001"]

    def test_domains_are_independent_on_the_same_tree(self) -> None:
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

    def test_imports_are_resolved_at_their_use_sites(self) -> None:
        """Rebinding must not retroactively invalidate an earlier route or query."""
        source = textwrap.dedent("""\
            from fastapi import APIRouter
            from sqlalchemy.engine import Result
            router = APIRouter()
            @router.get('/before')
            def before(result: Result):
                rows = list(result.all())
                result = other
                other_rows = list(result.all())
                return rows
            router = unknown
            @router.get('/after')
            def after():
                return {}
            """)
        findings = check_patterns(ast.parse(source), source)
        assert sorted((finding.line, finding.code) for finding in findings) == [(4, "PY009"), (6, "PY003")]

    def test_nested_scopes_restore_domain_bindings(self) -> None:
        """A shadowing nested helper must not clear its enclosing query result."""
        source = textwrap.dedent("""\
            from sqlalchemy.engine import Result
            def fetch(result: Result):
                def helper(result):
                    return list(result.all())
                rows = list(result.all())
                return rows
            """)
        assert [(finding.line, finding.code) for finding in check_patterns(ast.parse(source), source)] == [(5, "PY003")]

    def test_comment_and_ast_locations_use_one_based_columns(self) -> None:
        """Both native diagnostic sources share the public location convention."""
        source = "from src.errors import ConflictError\n#bad\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text(source)
            warnings = check_file(path)
        assert [(warning.line, warning.column, warning.code) for warning in warnings] == [(1, 1, "PY013"), (2, 1, "CM002"), (2, 1, "CM003")]
