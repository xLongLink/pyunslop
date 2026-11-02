import pytest
from tests.support import CheckNative


@pytest.mark.parametrize(
    "statement",
    [
        "rows = list(result.all())\n    return rows",
        "rows: Sequence[User] = list(result.fetchall())\n    return rows",
        "return list(result.all())",
    ],
)
def test_reports_sequence_compatible_row_copies(check_native: CheckNative, statement: str) -> None:
    """Review copies in local assignments and explicit sequence contracts."""

    # Arrange
    source = f"from collections.abc import Sequence\nfrom sqlalchemy.engine import Result\ndef consume(result: Result) -> Sequence[User]:\n    {statement}\n"

    # Act
    findings = check_native(source)

    # Assert
    assert [finding.code for finding in findings] == ["SLOP006"]


EXEMPTIONS = (
    pytest.param(
        "from sqlalchemy.engine import Result\ndef consume(result: Result):\n    rows = result.all()\n    return rows\n", id="no-copy"
    ),
    pytest.param(
        "from sqlalchemy.engine import Result\ndef consume(result: Result):\n    rows: list[User] = list(result.all())\n    return rows\n",
        id="mutable-assignment",
    ),
    # Earlier annotations remain authoritative after a later assignment.
    pytest.param(
        "from sqlalchemy.engine import Result\ndef consume(result: Result):\n    rows: list[User]\n    rows = list(result.all())\n    return rows\n",
        id="prior-mutable-annotation",
    ),
    # Unknown consumers may require a concrete mutable list.
    pytest.param(
        "from sqlalchemy.engine import Result\ndef consume(result: Result):\n    return list(result.all())\n", id="unknown-return-contract"
    ),
    pytest.param(
        "from sqlalchemy.engine import Result\ndef consume(result: Result):\n    use(list(result.all()))\n", id="unknown-consumer"
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_intentional_or_unknown_list_consumers(check_native: CheckNative, source: str) -> None:
    """Keep copies when mutability or consumer requirements are not known."""

    # Act
    findings = check_native(source)

    # Assert
    assert findings == []
