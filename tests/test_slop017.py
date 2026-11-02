import pytest
from tests.support import RunCLI, CheckNative, native_codes


@pytest.mark.parametrize("consumer", ["tuple", "frozenset"])
def test_reports_direct_iterable_only_materialization(run_cli: RunCLI, consumer: str) -> None:
    """Review simple eager lists passed directly to iterable-only builtins."""

    # Arrange
    source = f"total = {consumer}([value * 2 for value in values])\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP017"]


@pytest.mark.parametrize("consumer", ["sum", "min", "max", "tuple", "set", "frozenset"])
def test_reports_adjacent_single_use_temporary(run_cli: RunCLI, consumer: str) -> None:
    """Follow a function-local list used only by its next statement."""

    # Arrange
    source = f"def total(values):\n    amounts = [value * 2 for value in values]\n    return {consumer}(amounts)\n"

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == ["SLOP017"]


EXEMPTIONS = (
    pytest.param("total = tuple(value * 2 for value in values)\n", id="generator"),
    pytest.param("total = tuple([load(value) for value in values])\n", id="visible-call"),
    pytest.param("total = any([item.flag for item in items])\n", id="short-circuit-any"),
    pytest.param("total = all([item.flag for item in items])\n", id="short-circuit-all"),
    pytest.param("total = tuple([value for value in values if value])\n", id="filtered-comprehension"),
    pytest.param("async def total(values):\n    return tuple([value async for value in values])\n", id="async-comprehension"),
    # Reuse and intervening work preserve an eager snapshot's evaluation time.
    pytest.param(
        "def total(values):\n    amounts = [value * 2 for value in values]\n    log(amounts)\n    return sum(amounts)\n",
        id="reused-snapshot",
    ),
    pytest.param(
        "def total(values):\n    amounts = [value * 2 for value in values]\n    mutate(values)\n    return sum(amounts)\n",
        id="intervening-work",
    ),
    # A parameter named sum is not the builtin iterable consumer.
    pytest.param(
        "def total(values, sum):\n    amounts = [value * 2 for value in values]\n    return sum(amounts)\n", id="shadowed-builtin"
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_evaluation_and_snapshot_boundaries(run_cli: RunCLI, source: str) -> None:
    """Do not assume laziness preserves calls, filtering, or reused snapshots."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


@pytest.mark.parametrize(("consumer", "code"), [("sum", "C419"), ("min", "C419"), ("max", "C419"), ("set", "C403")])
def test_delegates_direct_comprehensions_to_real_ruff(run_cli: RunCLI, consumer: str, code: str) -> None:
    """Protect the documented Ruff boundary without duplicating native findings."""

    # Arrange
    source = f"total = {consumer}([value * 2 for value in values])\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == []
    assert f": {code} " in result.stdout


def test_nested_temporary_lists_keep_their_function_owner(check_native: CheckNative) -> None:
    """Analyze nested temporaries independently and resume the enclosing function."""
    source = "def outer(values):\n    async def inner():\n        pieces = [value * 2 for value in values]\n        return sum(pieces)\n    amounts = [value * 2 for value in values]\n    return sum(amounts)\n"

    # Act
    findings = check_native(source)

    # Assert
    assert [(finding.code, finding.line) for finding in findings] == [("SLOP017", 3), ("SLOP017", 5)]
