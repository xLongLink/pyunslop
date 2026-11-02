import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize(
    "body",
    [
        "await session.commit()\n    await session.refresh(user)",
        "if ready:\n        await session.commit()\n        await session.refresh(user)",
    ],
)
def test_reports_immediate_same_session_refresh(run_cli: RunCLI, body: str) -> None:
    """Recognize adjacent commit/refresh pairs in ordinary and compound blocks."""

    # Arrange
    source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def save(session: AsyncSession, user):\n    {body}\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP022"]
    assert "expire_on_commit, server defaults, and required relationships" in result.stdout


EXEMPTIONS = (
    # Missing refreshes and different session identities are not adjacent pairs.
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def save(session: AsyncSession, user):\n    await session.commit()\n",
        id="no-refresh",
    ),
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def save(session: AsyncSession, other: AsyncSession, user):\n    await session.commit()\n    await other.refresh(user)\n",
        id="different-session",
    ),
    # Adjacency and recognized session provenance are both required.
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncSession\nasync def save(session: AsyncSession, user):\n    await session.commit()\n    consume(user)\n    await session.refresh(user)\n",
        id="intervening-work",
    ),
    pytest.param("async def save(session, user):\n    await session.commit()\n    await session.refresh(user)\n", id="unknown-session"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_nonadjacent_and_other_session_refreshes(run_cli: RunCLI, source: str) -> None:
    """Require both recognized provenance and immediate same-session adjacency."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
