import ast
import tempfile
import textwrap
import unittest
from pathlib import Path
from pyunslop import check_file
from pyunslop.analysis import check_patterns

IMPORTS = """\
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence
"""


def findings(source: str) -> list[tuple[int, str]]:
    """Resolve query warnings using shared SQLAlchemy imports for each fixture."""
    tree = ast.parse(IMPORTS + textwrap.dedent(source))
    return [(node.lineno, code) for node, code, _ in check_patterns(tree)]


class QueryRuleTests(unittest.TestCase):
    """Check query-result provenance, contracts, and consumption patterns."""

    def codes(self, source: str) -> list[str]:
        """Return only the warning codes for a query fixture."""
        return [code for _, code in findings(source)]

    def test_py001_query_methods_and_consumers(self) -> None:
        """Detect unnamed results across query APIs and consuming method chains."""
        for method in ("execute", "scalars", "stream", "stream_scalars"):
            for chain in ("all()", "first()", "scalars().all()", "unique().all()"):
                with self.subTest(method=method, chain=chain):
                    source = f"async def fetch(s: AsyncSession):\n    return (await s.{method}(stmt)).{chain}\n"
                    expected = ["PY108", "PY001"] if method == "execute" and chain == "scalars().all()" else ["PY001"]
                    assert self.codes(source) == expected

    def test_named_result_is_allowed(self) -> None:
        """Allow separately named query results returned through a sequence contract."""
        source = """
        async def fetch(session: AsyncSession) -> Sequence[User]:
            result = await session.scalars(statement)
            return result.all()
        """
        assert self.codes(source) == []

    def test_py002_list_contract_on_direct_query_return(self) -> None:
        """Recommend sequence return types for direct query-row returns."""
        for expression in ("list(result.all())", "result.all()"):
            with self.subTest(expression=expression):
                source = f"async def fetch(s: AsyncSession) -> list[User]:\n    result = await s.scalars(stmt)\n    return {expression}\n"
                assert self.codes(source) == ["PY002"]

    def test_py002_typing_list_alias_and_string_annotation(self) -> None:
        """Resolve imported List aliases inside quoted return annotations."""
        source = """
        from typing import List as MutableList
        async def fetch(s: AsyncSession) -> "MutableList[User]":
            result = await s.execute(stmt)
            return list(result.scalars().all())
        """
        assert self.codes(source) == ["PY002", "PY108"]

    def test_py002_reports_once_per_function(self) -> None:
        """Report a return-contract issue once even with multiple offending returns."""
        source = """
        async def fetch(s: AsyncSession) -> list[User]:
            result = await s.scalars(stmt)
            if condition:
                return list(result.all())
            return result.all()
        """
        assert self.codes(source) == ["PY002"]

    def test_py003_sequence_return_and_assignment(self) -> None:
        """Detect redundant copies in assignments and sequence-compatible returns."""
        for statement in ("return list(result.all())", "users = list(result.all())", "users: Sequence[User] = list(result.all())"):
            with self.subTest(statement=statement):
                source = f"async def fetch(s: AsyncSession) -> Sequence[User]:\n    result = await s.scalars(stmt)\n    {statement}\n"
                assert self.codes(source) == ["PY003"]

    def test_py003_preserves_explicit_mutable_contracts(self) -> None:
        """Retain copies when list contracts or unknown consumers may require them."""
        for statement in (
            "users: list[User] = list(result.all())",
            "users: list[User]\n    users = list(result.all())",
            "consume(list(result.all()))",
            "return list(result.all())",
        ):
            # Act / Assert: every mutable or unknown contract must retain its copy.
            with self.subTest(statement=statement):
                source = f"async def fetch(s: AsyncSession):\n    result = await s.scalars(stmt)\n    {statement}\n"
                assert self.codes(source) == []

    def test_import_aliases_and_session_constructor(self) -> None:
        """Recognize module aliases and locally constructed async sessions."""
        source = """
        import sqlalchemy.ext.asyncio as sa
        async def fetch():
            session = sa.AsyncSession(engine)
            users = (await session.execute(stmt)).all()
        """
        assert self.codes(source) == ["PY001"]

    def test_sqlmodel_exec(self) -> None:
        """Recognize SQLModel's exec API through an imported session alias."""
        source = """
        from sqlmodel.ext.asyncio.session import AsyncSession as ModelSession
        async def fetch(s: ModelSession):
            return (await s.exec(stmt)).all()
        """
        assert self.codes(source) == ["PY001"]

    def test_session_factory_context_manager(self) -> None:
        """Track sessions yielded by known async session factories."""
        source = """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        sessions = async_sessionmaker(engine)
        async def fetch():
            async with sessions() as session:
                return (await session.execute(stmt)).scalars().all()
        """
        assert self.codes(source) == ["PY108", "PY001"]

    def test_typed_result_parameter(self) -> None:
        """Use known result annotations even without a local query assignment."""
        source = """
        from sqlalchemy.engine import ScalarResult
        def consume(result: ScalarResult[User]) -> Sequence[User]:
            return list(result.all())
        """
        assert self.codes(source) == ["PY003"]

    def test_unrelated_apis_and_plain_lists_are_ignored(self) -> None:
        """Avoid matching unrelated sessions and ordinary list-returning code."""
        source = """
        from other_library import AsyncSession as OtherSession
        async def fetch(session: OtherSession) -> list[User]:
            result = await session.execute(stmt)
            users = list(result.all())
            return (await session.execute(stmt)).all()
        def values() -> list[int]:
            return list(range(10))
        """
        assert self.codes(source) == []

    def test_untyped_session_name_is_not_enough(self) -> None:
        """Require library provenance rather than a variable named session."""
        source = """
        async def fetch(session):
            result = await session.execute(stmt)
            users = list(result.all())
            return (await session.execute(stmt)).all()
        """
        assert self.codes(source) == []

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
        assert self.codes(source) == []

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
        assert self.codes(source) == []

    def test_scalar_values_are_not_result_objects(self) -> None:
        """Distinguish scalar values from iterable query-result objects."""
        source = """
        async def fetch(s: AsyncSession):
            return (await s.scalar(stmt)).all()
        """
        assert self.codes(source) == []

    def test_loop_target_does_not_inherit_result_provenance(self) -> None:
        """Clear a previous result binding when it becomes a loop target."""
        source = """
        async def fetch(s: AsyncSession):
            result = await s.execute(stmt)
            for result in other_results:
                users = list(result.all())
        """
        assert self.codes(source) == []

    def test_argument_mutable_contract_is_preserved(self) -> None:
        """Retain an explicit list contract when assigning to a parameter."""
        source = """
        async def fetch(s: AsyncSession, users: list[User]):
            result = await s.execute(stmt)
            users = list(result.all())
        """
        assert self.codes(source) == []

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
        assert self.codes(source) == []

    def test_sync_sqlmodel_query_results(self) -> None:
        """Recognize redundant copies from synchronous SQLModel results."""
        source = """
        from sqlmodel import Session
        def fetch(s: Session) -> Sequence[User]:
            result = s.exec(stmt)
            return list(result.all())
        """
        assert self.codes(source) == ["PY003"]

    def test_shadowed_list_is_not_a_copy(self) -> None:
        """Avoid treating a shadowed list callable as the builtin conversion."""
        source = """
        async def fetch(s: AsyncSession, list):
            result = await s.execute(stmt)
            users = list(result.all())
        """
        assert self.codes(source) == []

    def test_warning_location_and_integration(self) -> None:
        """Preserve one-based query warning locations in the public file API."""
        source = IMPORTS + "async def fetch(s: AsyncSession):\n    return (await s.execute(stmt)).all()\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "query.py"
            path.write_text(source)
            warnings = check_file(path)
        assert [(w.code, w.line, w.column) for w in warnings] == [("PY001", 4, 12)]


if __name__ == "__main__":
    unittest.main()
