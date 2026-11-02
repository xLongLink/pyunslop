import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("result_type", ["Result", "ScalarResult", "MappingResult", "CursorResult"])
def test_reports_materializing_buffered_loop_inputs(run_cli: RunCLI, result_type: str) -> None:
    """Recognize buffered result annotations and their transformed values."""

    # Arrange
    source = f"from sqlalchemy.engine import {result_type} as Rows\ndef process(result: Rows):\n    for row in result.unique().all():\n        consume(row)\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP007"]


EXEMPTIONS = (
    # Direct iteration needs no change; streaming results have different semantics.
    pytest.param(
        "from sqlalchemy.engine import Result\ndef process(result: Result):\n    for row in result:\n        consume(row)\n",
        id="direct-iteration",
    ),
    pytest.param(
        "from sqlalchemy.ext.asyncio import AsyncResult\ndef process(result: AsyncResult):\n    for row in result.all():\n        consume(row)\n",
        id="streaming-result",
    ),
    # Batching and asynchronous consumption are deliberate iteration contracts.
    pytest.param(
        "from sqlalchemy.engine import Result\ndef process(result: Result):\n    for row in result.yield_per(100).all():\n        consume(row)\n",
        id="yield-per",
    ),
    pytest.param(
        "from sqlalchemy.engine import Result\nasync def process(result: Result):\n    async for row in result.all():\n        consume(row)\n",
        id="async-iteration",
    ),
    # Do not infer single-use buffering from reused rows or unknown objects.
    pytest.param(
        "from sqlalchemy.engine import Result\ndef process(result: Result):\n    rows = result.all()\n    consume(rows)\n    for row in rows:\n        consume(row)\n",
        id="reused-materialization",
    ),
    pytest.param("def process(result):\n    for row in result.all():\n        consume(row)\n", id="unknown-result"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_streaming_async_and_reused_rows(run_cli: RunCLI, source: str) -> None:
    """Keep materialization when buffering or single-use semantics are absent."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
