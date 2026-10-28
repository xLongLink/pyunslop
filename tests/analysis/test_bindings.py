import ast
import textwrap
import unittest
from tests.support import query_codes, check_patterns


class AnalysisTests(unittest.TestCase):
    """Exercise analyzer boundaries and shared parsing through observable results."""

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


class QueryBindingTests(unittest.TestCase):
    """Check query-result provenance, contracts, and consumption patterns."""

    def test_reassignments_and_parameter_shadowing_clear_provenance(self) -> None:
        """Forget query provenance when local bindings shadow or replace it."""
        source = """
        session = AsyncSession(engine)
        async def fetch(session):
            return (await session.execute(stmt)).all()
        async def other(s: AsyncSession):
            result = await s.execute(stmt)
            result = unrelated()
            users = list(result.all())
        """
        assert query_codes(source) == []

    def test_conditional_reassignment_does_not_leak_provenance(self) -> None:
        """Keep only result provenance common to both branch outcomes."""
        source = """
        async def fetch(s: AsyncSession):
            if condition:
                result = await s.execute(stmt)
            else:
                result = unrelated()
            users = list(result.all())
        """
        assert query_codes(source) == []

    def test_loop_target_does_not_inherit_result_provenance(self) -> None:
        """Clear a previous result binding when it becomes a loop target."""
        source = """
        async def fetch(s: AsyncSession):
            result = await s.execute(stmt)
            for result in other_results:
                users = list(result.all())
        """
        assert query_codes(source) == []

    def test_argument_mutable_contract_is_preserved(self) -> None:
        """Retain an explicit list contract when assigning to a parameter."""
        source = """
        async def fetch(s: AsyncSession, users: list[User]):
            result = await s.execute(stmt)
            users = list(result.all())
        """
        assert query_codes(source) == []

    def test_conditional_mutable_contract_is_not_lost(self) -> None:
        """Avoid recommending copy removal when a branch requires a list."""
        source = """
        async def fetch(s: AsyncSession):
            result = await s.execute(stmt)
            if condition:
                users: list[User]
            else:
                users: Sequence[User]
            users = list(result.all())
        """
        assert query_codes(source) == []

    def test_shadowed_list_is_not_a_copy(self) -> None:
        """Avoid treating a shadowed list callable as the builtin conversion."""
        source = """
        async def fetch(s: AsyncSession, list):
            result = await s.execute(stmt)
            users = list(result.all())
        """
        assert query_codes(source) == []
