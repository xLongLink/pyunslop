from tests.support import codes


def test_allowlisted_classes() -> None:
    """Require names for direct and property-chained domain method calls."""
    source = """
    async def fetch():
        usage = await Postgres(host, port).usage()
        logs = await Kubernetes(config).applications.logs(name)
    """
    assert codes(source) == ["SLOP009", "SLOP009"]


def test_import_aliases_and_module_qualified_classes() -> None:
    """Resolve allowlisted constructors through import aliases and modules."""
    source = """
    from domain import Postgres as Database
    import domain as d
    usage = Database(host).usage()
    logs = d.Kubernetes(config).applications.logs(name)
    """
    assert codes(source) == ["SLOP009", "SLOP009"]


def test_named_instances_and_other_classes_are_allowed() -> None:
    """Allow named instances and fluent APIs outside the class allowlist."""
    source = """
    database = Postgres(host)
    usage = database.usage()
    logs = OtherClient(config).applications.logs(name)
    """
    assert codes(source) == []


def test_allowlisted_local_class() -> None:
    """Apply the explicit allowlist to locally declared domain classes."""
    source = """
    class Postgres:
        pass
    usage = Postgres(host).usage()
    """
    assert codes(source) == ["SLOP009"]


def test_shadowed_alias_is_ignored() -> None:
    """Forget an imported class alias when a parameter shadows it."""
    source = """
    from domain import Postgres as Database
    def fetch(Database):
        return Database(host).usage()
    """
    assert codes(source) == []
