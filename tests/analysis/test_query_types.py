import unittest
from tests.support import query_codes


class QueryTypeTests(unittest.TestCase):
    """Check query-result provenance, contracts, and consumption patterns."""

    def test_import_aliases_and_session_constructor(self) -> None:
        """Recognize module aliases and locally constructed async sessions."""
        source = """
        import sqlalchemy.ext.asyncio as sa
        async def fetch():
            session = sa.AsyncSession(engine)
            users = (await session.execute(stmt)).all()
        """
        assert query_codes(source) == ["PY001"]

    def test_sqlmodel_exec(self) -> None:
        """Recognize SQLModel's exec API through an imported session alias."""
        source = """
        from sqlmodel.ext.asyncio.session import AsyncSession as ModelSession
        async def fetch(s: ModelSession):
            return (await s.exec(stmt)).all()
        """
        assert query_codes(source) == ["PY001"]

    def test_session_factory_context_manager(self) -> None:
        """Track sessions yielded by known async session factories."""
        source = """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        sessions = async_sessionmaker(engine)
        async def fetch():
            async with sessions() as session:
                return (await session.execute(stmt)).scalars().all()
        """
        assert query_codes(source) == ["PY108", "PY001"]

    def test_typed_result_parameter(self) -> None:
        """Use known result annotations even without a local query assignment."""
        source = """
        from sqlalchemy.engine import ScalarResult
        def consume(result: ScalarResult[User]) -> Sequence[User]:
            return list(result.all())
        """
        assert query_codes(source) == ["PY003"]

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
        assert query_codes(source) == []

    def test_untyped_session_name_is_not_enough(self) -> None:
        """Require library provenance rather than a variable named session."""
        source = """
        async def fetch(session):
            result = await session.execute(stmt)
            users = list(result.all())
            return (await session.execute(stmt)).all()
        """
        assert query_codes(source) == []

    def test_scalar_values_are_not_result_objects(self) -> None:
        """Distinguish scalar values from iterable query-result objects."""
        source = """
        async def fetch(s: AsyncSession):
            return (await s.scalar(stmt)).all()
        """
        assert query_codes(source) == []

    def test_sync_sqlmodel_query_results(self) -> None:
        """Recognize redundant copies from synchronous SQLModel results."""
        source = """
        from sqlmodel import Session
        def fetch(s: Session) -> Sequence[User]:
            result = s.exec(stmt)
            return list(result.all())
        """
        assert query_codes(source) == ["PY003"]
