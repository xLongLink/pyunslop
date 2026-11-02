import pytest
from tests.support import RunCLI, native_codes

CANDIDATES = (
    pytest.param(
        "from services import Postgres\nasync def inspect_database(config):\n    return await Postgres(config).usage()\n",
        id="documented-instance",
    ),
    pytest.param("from services import Postgres as Database\nusage = Database(config).usage()\n", id="imported-alias"),
    pytest.param("import services as domain\nlogs = domain.Kubernetes(config).applications.logs(name)\n", id="module-and-attribute-chain"),
)


@pytest.mark.parametrize("source", CANDIDATES)
def test_requires_names_for_allowlisted_domain_instances(run_cli: RunCLI, source: str) -> None:
    """Recognize imported aliases and methods reached through attributes."""

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP009"]


EXEMPTIONS = (
    pytest.param(
        "from services import Postgres\nasync def inspect_database(config):\n    database = Postgres(config)\n    return await database.usage()\n",
        id="named-instance",
    ),
    pytest.param("from services import OtherClient\nusage = OtherClient(config).usage()\n", id="other-class"),
    # Parameter bindings override imported constructor aliases.
    pytest.param(
        "from services import Postgres as Database\ndef inspect_database(Database):\n    return Database(config).usage()\n",
        id="shadowed-alias",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_named_instances_and_other_fluent_apis(run_cli: RunCLI, source: str) -> None:
    """Apply only the documented class allowlist with valid provenance."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
