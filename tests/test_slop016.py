import pytest
from tests.support import RunCLI, native_codes

CANDIDATES = (
    pytest.param("rows = [Row(value=(value := item.value), doubled=value * 2) for item in items]\n", id="list-comprehension"),
    pytest.param("rows = {Row(value=(value := item.value), doubled=value * 2) for item in items}\n", id="set-comprehension"),
    pytest.param("rows = {item.id: Row(value=(value := item.value), doubled=value * 2) for item in items}\n", id="dict-comprehension"),
    pytest.param("rows = (Row(value=(value := item.value), doubled=value * 2) for item in items)\n", id="generator"),
)


@pytest.mark.parametrize("source", CANDIDATES)
def test_reports_constructor_argument_dependencies(run_cli: RunCLI, source: str) -> None:
    """Find later arguments that depend on a walrus binding in a comprehension."""

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP016"]


EXEMPTIONS = (
    pytest.param(
        "rows = []\nfor item in items:\n    value = item.value\n    rows.append(Row(value=value, doubled=value * 2))\n", id="explicit-loop"
    ),
    pytest.param("rows = [Row(value=(value := item.value), doubled=item.other * 2) for item in items]\n", id="independent-binding"),
    pytest.param("row = Row(value=(value := item.value), doubled=value * 2)\n", id="outside-comprehension"),
    # Ordinary functions and reads in the same argument are not constructor dependencies.
    pytest.param("rows = [build(value=(value := item.value), doubled=value * 2) for item in items]\n", id="ordinary-function"),
    pytest.param("rows = [Row(((value := item), value), other=item) for item in items]\n", id="same-argument-read"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_independent_bindings_and_explicit_loops(run_cli: RunCLI, source: str) -> None:
    """Restrict the rule to dependencies across constructor arguments."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


@pytest.mark.parametrize(
    ("source", "count"),
    [
        pytest.param(
            "rows = [[Row(value=(value := item), doubled=value * 2) for item in group] for group in groups]\n", 1, id="nested-output"
        ),
        # Different constructors can expose the same binding.
        pytest.param(
            "rows = [Outer([Inner(value=(value := item), doubled=value * 2) for item in group], later=value) for group in groups]\n",
            1,
            id="overlapping-constructor-dependencies",
        ),
        # Nested filters remain part of the enclosing output expression.
        pytest.param(
            "rows = [[Row(value=(value := item), later=value) for item in Rows(group) if Check(flag=(flag := item), later=flag)] for group in groups]\n",
            2,
            id="nested-iterable-and-filter",
        ),
    ],
)
def test_nested_comprehensions_report_each_binding_once(run_cli: RunCLI, source: str, count: int) -> None:
    """Preserve nested calls and deduplicate bindings shared by constructor scans."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == ["SLOP016"] * count
