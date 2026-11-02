import pytest
from tests.support import RunCLI, native_codes


def test_reports_borrowed_client_only_class(run_cli: RunCLI) -> None:
    """Review a class with only borrowed-client state and forwarding behavior."""

    # Arrange
    source = """
        class Users:
            def __init__(self, client):
                self.client = client

            def fetch(self):
                return self.client.fetch_users()

        users = Users(client).fetch()
    """

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP021"]


EXEMPTIONS = (
    pytest.param("def fetch_users(client):\n    return client.fetch_users()\nusers = fetch_users(client)\n", id="namespaced-function"),
    pytest.param(
        "class Users:\n    def __init__(self, config):\n        self.client = API(config)\n    def fetch(self):\n        return self.client.fetch_users()\n",
        id="owned-client",
    ),
    # Extra state and inheritance make these more than plain borrowed-client wrappers.
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n        self.cache = {}\n    def fetch(self):\n        return self.client.fetch_users()\n",
        id="extra-state",
    ),
    pytest.param(
        "class Users(Interface):\n    def __init__(self, client):\n        self.client = client\n    def fetch(self):\n        return self.client.fetch_users()\n",
        id="inheritance-boundary",
    ),
    # Documentation and properties establish deliberate service contracts.
    pytest.param(
        'class Users:\n    """Keep the service API boundary."""\n    def __init__(self, client):\n        self.client = client\n    def fetch(self):\n        return self.client.fetch_users()\n',
        id="documented-boundary",
    ),
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n    @property\n    def users(self):\n        return self.client.fetch_users()\n",
        id="property",
    ),
    # Context-manager hooks carry resource-lifetime behavior.
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n    def __enter__(self):\n        return self.client\n",
        id="lifecycle-hook",
    ),
    # Escaping self exposes more than the borrowed client.
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n    def register(self):\n        return register(self)\n",
        id="passing-self",
    ),
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n    def fetch(self):\n        return self\n",
        id="returning-self",
    ),
    # State changes outside construction establish meaningful behavior.
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n    def replace(self, client):\n        self.client = client\n",
        id="rebinding-client",
    ),
    pytest.param(
        "class Users:\n    def __init__(self, client):\n        self.client = client\n    def clear(self):\n        del self.client\n",
        id="deleting-client",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_ownership_state_and_intentional_boundaries(run_cli: RunCLI, source: str) -> None:
    """Keep classes that do more than expose a directly borrowed client."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
