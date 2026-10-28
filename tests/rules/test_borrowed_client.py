import pytest
from tests.support import codes

OWNERSHIP_BOUNDARIES = (
    "class Client:\n    def __init__(self, config):\n        self._client = API(config)\n    def fetch(self):\n        return self._client.fetch()\n",
    "class Client:\n    def __init__(self, client):\n        self._client = client\n        self._cache = {}\n    def fetch(self):\n        return self._client.fetch()\n",
    "class Client(Interface):\n    def __init__(self, client):\n        self._client = client\n    def fetch(self):\n        return self._client.fetch()\n",
)


def test_borrowed_client_only_class() -> None:
    """Review a class whose only state and behavior wrap a borrowed client."""
    source = """
    class Organizations:
        def __init__(self, client):
            self._client = client
        async def delete(self, organization_id):
            await utils.delete_namespace(await self._client.api(), organization_id)
    """
    assert codes(source) == ["SLOP021"]


@pytest.mark.parametrize("source", OWNERSHIP_BOUNDARIES)
def test_owned_client_extra_state_and_framework_boundaries_are_preserved(source: str) -> None:
    """Preserve owned clients, extra instance state, and inherited contracts."""
    assert codes(source) == []
