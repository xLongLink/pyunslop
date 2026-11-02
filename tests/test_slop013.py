import pytest
from tests.support import RunCLI, CheckNative, native_codes


@pytest.mark.parametrize("values", ["[1]", "(1,)", "[(1,)]"])
def test_reports_single_literal_pytest_cases(run_cli: RunCLI, values: str) -> None:
    """Recognize redundant one-case lists and tuples through the CLI."""

    # Arrange
    source = f"import pytest\n@pytest.mark.parametrize('value', {values})\ndef test_positive(value):\n    assert value > 0\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP013"]


COLLECTION_OPTIONS = (
    # Dynamic values and explicit collection metadata are not redundant cases.
    pytest.param("'value', [1, 2]", id="multiple-cases"),
    pytest.param("'value', cases", id="dynamic-cases"),
    pytest.param("'value', [pytest.param(1)]", id="pytest-param"),
    pytest.param("'value', [1], ids=['positive']", id="explicit-id"),
    pytest.param("'value', [1], scope='module'", id="explicit-scope"),
    pytest.param("'value', [1], indirect=True", id="indirect-fixture"),
)


@pytest.mark.parametrize("options", COLLECTION_OPTIONS)
def test_preserves_fixture_and_collection_behavior(run_cli: RunCLI, options: str) -> None:
    """Keep explicit collection contracts rather than simplifying their syntax."""

    # Arrange
    source = f"import pytest\n@pytest.mark.parametrize({options})\ndef test_positive(value):\n    assert value > 0\n"

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


EXEMPTIONS = (
    pytest.param("def test_positive():\n    assert 1 > 0\n", id="direct-test"),
    pytest.param(
        "import pytest\n@pytest.mark.parametrize('value', [1])\ndef test_positive(value, request):\n    assert request.node.callspec\n",
        id="request-fixture",
    ),
    # Module-level hooks can inspect case metadata without using request.
    pytest.param(
        "import pytest\ndef pytest_generate_tests(metafunc):\n    pass\n@pytest.mark.parametrize('value', [1])\ndef test_positive(value):\n    assert value > 0\n",
        id="collection-hook",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_request_and_collection_hook_exemptions(run_cli: RunCLI, source: str) -> None:
    """Honor metadata-sensitive tests and the documented direct-test rewrite."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


@pytest.mark.parametrize(
    ("parameters", "codes"),
    [("request, /, value", []), ("value, *, request", []), ("value, *request", ["SLOP013"]), ("value, **request", ["SLOP013"])],
)
def test_request_exemption_applies_only_to_fixed_parameters(check_native: CheckNative, parameters: str, codes: list[str]) -> None:
    """Do not mistake a variadic name for pytest's explicit request fixture."""
    source = f"import pytest\n@pytest.mark.parametrize('value', [1])\ndef test_positive({parameters}):\n    pass\n"

    # Act
    findings = check_native(source)

    # Assert
    assert [finding.code for finding in findings] == codes
