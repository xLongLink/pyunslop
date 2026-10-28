import ast
import pytest
from tests.support import codes, query_codes, check_patterns

SEQUENCE_CONSUMERS = ("return list(result.all())", "users = list(result.all())", "users: Sequence[User] = list(result.all())")


# Mutable and unknown consumers may require a list rather than a sequence.
MUTABLE_CONSUMERS = (
    "users: list[User] = list(result.all())",
    "users: list[User]\n    users = list(result.all())",
    "consume(list(result.all()))",
    "return list(result.all())",
)


def test_analysis_state_is_not_shared_between_files() -> None:
    """Keep imported session provenance local to one analyzer invocation."""
    typed = ast.parse(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(s: AsyncSession):\n    return (await s.execute(stmt)).all()\n"
    )
    unknown = ast.parse("async def fetch(s):\n    return (await s.execute(stmt)).all()\n")
    assert [finding.code for finding in check_patterns(typed)] == ["SLOP005"]
    assert check_patterns(unknown) == []

    # Reusing the typed tree must not retain another file's provenance.
    assert [finding.code for finding in check_patterns(typed)] == ["SLOP005"]


@pytest.mark.parametrize("method", ["execute", "scalars"])
def test_buffered_async_execute_and_scalars(method: str) -> None:
    """Avoid all() when buffered async-query results are consumed only by a loop."""
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(s: AsyncSession):\n    result = await s.{method}(stmt)\n    for row in result.all():\n        consume(row)\n"
    assert codes(source) == ["SLOP008"]


@pytest.mark.parametrize("result_type", ["Result", "ScalarResult", "MappingResult", "CursorResult"])
def test_buffered_result_annotations_and_transforms(result_type: str) -> None:
    """Retain buffering knowledge through known result annotations and transforms."""
    source = f"from sqlalchemy.engine import {result_type} as Rows\ndef consume(result: Rows):\n    for row in result.unique().all():\n        use(row)\n"
    assert codes(source) == ["SLOP008"]


def test_streaming_and_unknown_results_are_ignored() -> None:
    """Preserve materialization for streaming or unrecognized result types."""
    source = """
    from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult
    async def fetch(s: AsyncSession, async_result: AsyncResult, unknown):
        result = await s.stream(stmt)
        for row in result.all():
            consume(row)
        for row in async_result.all():
            consume(row)
        for row in unknown.all():
            consume(row)
    """
    assert codes(source) == []


def test_yield_per_and_async_iteration_are_ignored() -> None:
    """Leave batching and asynchronous iteration semantics unchanged."""
    source = """
    from sqlalchemy.engine import Result
    async def fetch(result: Result):
        for row in result.yield_per(100).all():
            consume(row)
        async for row in result.all():
            consume(row)
    """
    assert codes(source) == []


def test_materialization_used_elsewhere_is_ignored() -> None:
    """Preserve row lists reused or consumed by operations beyond direct iteration."""
    source = """
    from sqlalchemy.engine import Result
    def fetch(result: Result):
        rows = result.all()
        for row in rows:
            consume(row)
        for row in reversed(result.all()):
            consume(row)
    """
    assert codes(source) == []


def test_sqlmodel_col_and_import_aliases() -> None:
    """Recognize SQLModel column helpers imported under aliases."""
    source = """
    from sqlmodel import col as column
    statement = column(User.id).in_([member.user_id for member in members])
    """
    assert codes(source) == ["SLOP009"]


def test_sqlalchemy_column() -> None:
    """Recognize module-qualified SQLAlchemy column expressions."""
    source = """
    import sqlalchemy as sa
    expression = sa.column('id').in_([item.id for item in items])
    """
    assert codes(source) == ["SLOP009"]


def test_select_where_context() -> None:
    """Infer SQL expression ownership inside a known select statement."""
    source = """
    from sqlalchemy import select
    statement = select(User)
    statement = statement.where(User.id.in_([item.id for item in items]))
    """
    assert codes(source) == ["SLOP009"]


def test_generator_and_reused_list_are_allowed() -> None:
    """Accept existing generators and lists assigned outside the in_ call."""
    source = """
    from sqlmodel import col
    ids = [member.user_id for member in members]
    first = col(User.id).in_(ids)
    second = col(User.id).in_(member.user_id for member in members)
    """
    assert codes(source) == []


def test_unrelated_in_method_is_ignored() -> None:
    """Avoid inferring SQL semantics through unrelated method calls."""
    source = """
    from sqlalchemy import select
    custom.in_([member.id for member in members])
    statement = select(User).where(custom.consume(custom.in_([item.id for item in items])))
    """
    assert codes(source) == []


def test_scalar_api_preserves_cardinality() -> None:
    """Recommend scalars without dropping the one_or_none cardinality check."""
    source = """
    from sqlalchemy.ext.asyncio import AsyncSession
    async def fetch(s: AsyncSession):
        result = await s.execute(stmt)
        return result.scalars().one_or_none()
    """
    assert codes(source) == ["SLOP021"]


def test_single_column_unpacking() -> None:
    """Review loop unpacking from a known single-selection query."""
    source = """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    async def fetch(s: AsyncSession):
        result = await s.execute(select(User))
        for user, in result:
            consume(user)
    """
    assert codes(source) == ["SLOP021"]


def test_single_row_unpacking() -> None:
    """Review one-element row unpacking while retaining its cardinality check."""
    source = """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    async def fetch(s: AsyncSession):
        result = await s.execute(select(User))
        user, = result.one()
    """
    assert codes(source) == ["SLOP021"]


def test_multi_column_unpacking_is_preserved() -> None:
    """Retain row consumption when multiple selected columns are required."""
    source = """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    async def fetch(s: AsyncSession):
        result = await s.execute(select(User.id, User.name))
        for user_id, name in result:
            consume(user_id, name)
    """
    assert codes(source) == []


@pytest.mark.parametrize("expression", ["bool(result.all())", "len(result.all()) > 3"])
def test_direct_existence_or_threshold_materialization(expression: str) -> None:
    """Review rows loaded directly for truth or threshold comparisons."""
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def exists(s: AsyncSession):\n    result = await s.scalars(stmt)\n    return {expression}\n"
    assert codes(source) == ["SLOP022"]


def test_named_size_only_materialization() -> None:
    """Follow a named row list used only for a length comparison."""
    source = """
    from sqlalchemy.ext.asyncio import AsyncSession
    async def exists(s: AsyncSession):
        result = await s.scalars(stmt)
        rows = result.all()
        return len(rows) >= threshold
    """
    assert codes(source) == ["SLOP022"]


def test_rows_used_as_data_are_preserved() -> None:
    """Keep materialized rows when another consumer needs their data."""
    source = """
    from sqlalchemy.ext.asyncio import AsyncSession
    async def fetch(s: AsyncSession):
        result = await s.scalars(stmt)
        rows = result.all()
        consume(rows)
        return len(rows)
    """
    assert codes(source) == []


def test_immediate_refresh_candidate() -> None:
    """Review a refresh immediately following a same-session commit."""
    source = """
    from sqlalchemy.ext.asyncio import AsyncSession
    async def save(s: AsyncSession, item):
        s.add(item)
        await s.commit()
        await s.refresh(item)
        return item
    """
    assert codes(source) == ["SLOP025"]


def test_different_sessions_and_intervening_work_are_preserved() -> None:
    """Keep refreshes on other sessions or separated from commit by work."""
    source = """
    from sqlalchemy.ext.asyncio import AsyncSession
    async def save(s: AsyncSession, other: AsyncSession, item):
        await s.commit()
        await other.refresh(item)
        await s.commit()
        consume(item)
        await s.refresh(item)
    """
    assert codes(source) == []


def test_deduplication_is_local_to_one_analysis() -> None:
    """Rechecking the identical tree must neither lose nor duplicate findings."""

    # Arrange
    source = "from sqlalchemy.engine import Result\ndef fetch(result: Result) -> list[User]:\n    if condition:\n        return result.all()\n    return result.all()\n"
    tree = ast.parse(source)

    # Act
    first = check_patterns(tree)
    second = check_patterns(tree)

    # Assert
    assert [finding.code for finding in first] == ["SLOP006"]
    assert second == first


@pytest.mark.parametrize("chain", ["all()", "first()", "scalars().all()", "unique().all()"])
@pytest.mark.parametrize("method", ["execute", "scalars", "stream", "stream_scalars"])
def test_slop005_query_methods_and_consumers(chain: str, method: str) -> None:
    """Detect unnamed results across query APIs and consuming method chains."""
    source = f"async def fetch(s: AsyncSession):\n    return (await s.{method}(stmt)).{chain}\n"
    expected = ["SLOP021", "SLOP005"] if method == "execute" and chain == "scalars().all()" else ["SLOP005"]
    assert query_codes(source) == expected


def test_named_result_is_allowed() -> None:
    """Allow separately named query results returned through a sequence contract."""
    source = """
    async def fetch(session: AsyncSession) -> Sequence[User]:
        result = await session.scalars(statement)
        return result.all()
    """
    assert query_codes(source) == []


@pytest.mark.parametrize("expression", ["list(result.all())", "result.all()"])
def test_slop006_list_contract_on_direct_query_return(expression: str) -> None:
    """Recommend sequence return types for direct query-row returns."""
    source = f"async def fetch(s: AsyncSession) -> list[User]:\n    result = await s.scalars(stmt)\n    return {expression}\n"
    assert query_codes(source) == ["SLOP006"]


def test_slop006_typing_list_alias_and_string_annotation() -> None:
    """Resolve imported List aliases inside quoted return annotations."""
    source = """
    from typing import List as MutableList
    async def fetch(s: AsyncSession) -> "MutableList[User]":
        result = await s.execute(stmt)
        return list(result.scalars().all())
    """
    assert query_codes(source) == ["SLOP006", "SLOP021"]


def test_slop006_reports_once_per_function() -> None:
    """Report a return-contract issue once even with multiple offending returns."""
    source = """
    async def fetch(s: AsyncSession) -> list[User]:
        result = await s.scalars(stmt)
        if condition:
            return list(result.all())
        return result.all()
    """
    assert query_codes(source) == ["SLOP006"]


@pytest.mark.parametrize("statement", SEQUENCE_CONSUMERS)
def test_slop007_sequence_return_and_assignment(statement: str) -> None:
    """Detect redundant copies in assignments and sequence-compatible returns."""
    source = f"async def fetch(s: AsyncSession) -> Sequence[User]:\n    result = await s.scalars(stmt)\n    {statement}\n"
    assert query_codes(source) == ["SLOP007"]


@pytest.mark.parametrize("statement", MUTABLE_CONSUMERS)
def test_slop007_preserves_explicit_mutable_contracts(statement: str) -> None:
    """Retain copies when list contracts or unknown consumers may require them."""
    source = f"async def fetch(s: AsyncSession):\n    result = await s.scalars(stmt)\n    {statement}\n"
    assert query_codes(source) == []
