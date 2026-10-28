from tests.support import query_codes


def test_import_aliases_and_session_constructor() -> None:
    """Recognize module aliases and locally constructed async sessions."""
    source = """
    import sqlalchemy.ext.asyncio as sa
    async def fetch():
        session = sa.AsyncSession(engine)
        users = (await session.execute(stmt)).all()
    """
    assert query_codes(source) == ["SLOP005"]


def test_sqlmodel_exec() -> None:
    """Recognize SQLModel's exec API through an imported session alias."""
    source = """
    from sqlmodel.ext.asyncio.session import AsyncSession as ModelSession
    async def fetch(s: ModelSession):
        return (await s.exec(stmt)).all()
    """
    assert query_codes(source) == ["SLOP005"]


def test_session_factory_context_manager() -> None:
    """Track sessions yielded by known async session factories."""
    source = """
    from sqlalchemy.ext.asyncio import async_sessionmaker
    sessions = async_sessionmaker(engine)
    async def fetch():
        async with sessions() as session:
            return (await session.execute(stmt)).scalars().all()
    """
    assert query_codes(source) == ["SLOP019", "SLOP005"]


def test_typed_result_parameter() -> None:
    """Use known result annotations even without a local query assignment."""
    source = """
    from sqlalchemy.engine import ScalarResult
    def consume(result: ScalarResult[User]) -> Sequence[User]:
        return list(result.all())
    """
    assert query_codes(source) == ["SLOP007"]


def test_unrelated_apis_and_plain_lists_are_ignored() -> None:
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


def test_untyped_session_name_is_not_enough() -> None:
    """Require library provenance rather than a variable named session."""
    source = """
    async def fetch(session):
        result = await session.execute(stmt)
        users = list(result.all())
        return (await session.execute(stmt)).all()
    """
    assert query_codes(source) == []


def test_scalar_values_are_not_result_objects() -> None:
    """Distinguish scalar values from iterable query-result objects."""
    source = """
    async def fetch(s: AsyncSession):
        return (await s.scalar(stmt)).all()
    """
    assert query_codes(source) == []


def test_sync_sqlmodel_query_results() -> None:
    """Recognize redundant copies from synchronous SQLModel results."""
    source = """
    from sqlmodel import Session
    def fetch(s: Session) -> Sequence[User]:
        result = s.exec(stmt)
        return list(result.all())
    """
    assert query_codes(source) == ["SLOP007"]
