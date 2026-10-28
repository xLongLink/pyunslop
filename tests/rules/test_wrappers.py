import pytest
from tests.support import codes

MEANINGFUL_WRAPPERS = (
    "def fetch(value):\n    return other(value)\n",
    "def _fetch(value) -> User:\n    return other(value)\n",
    "@hook\ndef _fetch(value):\n    return other(value)\n",
    "def _fetch(value):\n    return other(transform(value))\n",
)


def test_private_transparent_wrapper() -> None:
    """Review exact private forwarding wrappers without added behavior."""
    assert codes("def _fetch(value):\n    return fetch(value)\n") == ["SLOP023"]


@pytest.mark.parametrize("source", MEANINGFUL_WRAPPERS)
def test_public_contracts_decorators_and_transformations_are_preserved(source: str) -> None:
    """Preserve public, typed, decorated, and transforming wrapper boundaries."""
    assert codes(source) == []


def test_empty_test_client_subclass() -> None:
    """Review a known test-client subclass that adds no behavior."""
    source = "from fastapi.testclient import TestClient as FastAPITestClient\nclass TestClient(FastAPITestClient):\n    pass\n"
    assert codes(source) == ["SLOP023"]


def test_framework_subclass_and_documented_boundary_are_preserved() -> None:
    """Keep framework subclasses and intentionally documented compatibility aliases."""
    source = '''
    from unittest import TestCase
    class Tests(TestCase):
        pass
    class _Boundary(Base):
        """Public compatibility boundary."""
        pass
    '''
    assert codes(source) == ["SLOP016"]


def test_private_framework_hook_is_preserved() -> None:
    """Retain inherited private hooks even when they only forward a call."""
    source = """
    class Handler(Framework):
        def _dispatch(self, request):
            return dispatch(self, request)
    """
    assert codes(source) == []
