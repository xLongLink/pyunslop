import pytest
from tests.support import RunCLI, native_codes

CANDIDATES = (
    pytest.param("def _fetch(value):\n    return fetch(value)\nresult = _fetch(value)\n", id="private-forwarder"),
    pytest.param("async def _fetch(value):\n    return await fetch(value)\n", id="async-forwarder"),
    pytest.param("class _Alias(Base):\n    pass\n", id="private-empty-subclass"),
    pytest.param("from fastapi.testclient import TestClient as Base\nclass TestClient(Base):\n    pass\n", id="test-client-subclass"),
)


@pytest.mark.parametrize("source", CANDIDATES)
def test_reports_transparent_private_boundaries(run_cli: RunCLI, source: str) -> None:
    """Review exact forwarding and the explicitly allowlisted empty subclasses."""

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP020"]


EXEMPTIONS = (
    pytest.param("result = fetch(value)\n", id="direct-call"),
    pytest.param("def fetch(value):\n    return other(value)\n", id="public-function"),
    pytest.param("def _fetch(value) -> User:\n    return fetch(value)\n", id="typed-contract"),
    pytest.param('def _fetch(value):\n    """Preserve the compatibility boundary."""\n    return fetch(value)\n', id="documented-contract"),
    pytest.param("@hook\ndef _fetch(value):\n    return fetch(value)\n", id="decorated-contract"),
    pytest.param("def _fetch(value):\n    return fetch(transform(value))\n", id="transformed-argument"),
    # Framework hooks and documented compatibility subclasses establish boundaries.
    pytest.param(
        "class Handler(Framework):\n    def _dispatch(self, request):\n        return dispatch(self, request)\n",
        id="inherited-framework-method",
    ),
    pytest.param('class _Boundary(Base):\n    """Public compatibility boundary."""\n    pass\n', id="documented-subclass"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_meaningful_contracts_and_framework_hooks(run_cli: RunCLI, source: str) -> None:
    """Keep wrappers whose signatures, documentation, or behavior add a boundary."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
