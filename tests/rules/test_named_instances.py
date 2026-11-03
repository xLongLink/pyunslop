from pathlib import Path
from tests.support import codes
from pyunslop.checker import check_file


def test_declared_classes_and_attribute_methods() -> None:
    """Require names for arbitrary classes and property-chained method calls."""
    source = """
    class Client:
        pass
    async def fetch():
        usage = await Client(host, port).usage()
        logs = await Client(config).applications.logs(name)
    """
    assert codes(source) == ["SLOP009", "SLOP009"]


def test_local_aliases_and_qualified_classes() -> None:
    """Follow assignment aliases and directly declared nested classes."""
    source = """
    class Services:
        class Client:
            pass
    Database = Services.Client
    usage = Database(host).usage()
    logs = Services.Client(config).applications.logs(name)
    """
    assert codes(source) == ["SLOP009", "SLOP009"]


def test_named_multiline_and_zero_argument_instances() -> None:
    """Allow multiline assignments and exempt zero-argument construction."""
    source = """
    class Client:
        pass
    client = Client(
        host,
    )
    other: Client = Client(
        host=host,
    )
    empty = Client()
    usage = client.usage()
    """
    assert codes(source) == []


def test_single_line_constructor_assignments() -> None:
    """Check positional and keyword construction in ordinary and annotated assignments."""
    source = """
    class Client:
        pass
    client = Client(host)
    other: Client = Client(host=host)
    """
    assert codes(source) == ["SLOP009", "SLOP009"]


def test_zero_argument_method_call_still_requires_assignment() -> None:
    """The formatting exemption does not exempt inline method invocation."""
    assert codes("class Client: pass\nClient().fetch()") == ["SLOP009"]


def test_multiline_inline_construction_reports_only_missing_assignment() -> None:
    """Multiline formatting alone does not make an inline instance named."""
    source = """
    class repository:
        pass
    repository(
        config,
    ).applications.fetch().decode()
    """
    assert codes(source) == ["SLOP009"]


def test_calling_an_instance_is_not_a_method_call() -> None:
    """Do not mistake callable instances for attribute-based method invocation."""
    assert codes("class Client: pass\nClient(config)()") == []


def test_shadowed_aliases_are_ignored() -> None:
    """Forget class evidence when parameters or assignments shadow it."""
    source = """
    class Client:
        pass
    Alias = Client
    def fetch(Alias):
        return Alias(host).usage()
    Alias = factory
    Alias(host).usage()
    """
    assert codes(source) == []


def test_factories_unresolved_imports_and_fluent_apis_are_ignored() -> None:
    """Do not guess class identities from imported names or capitalization."""
    source = """
    from unknown import Client
    import unknown as services
    def Factory(config):
        return config
    Client(config).fetch()
    services.Client(config).fetch()
    Factory(config).configure().build()
    builder(config).configure().build()
    Postgres(config).usage()
    Kubernetes(config).applications.logs(name)
    """
    assert codes(source) == []


def test_decorated_classes_are_ignored() -> None:
    """A decorator may replace a class with an ordinary factory."""
    assert codes("@factory\nclass Client: pass\nClient(config).fetch()") == []


def test_local_import_aliases_and_qualified_constructors(tmp_path: Path) -> None:
    """Resolve imported constructors from local source without executing it."""
    (tmp_path / "services.py").write_text("raise RuntimeError('must not execute')\nclass Client: pass\n")
    path = tmp_path / "consumer.py"
    path.write_text(
        "from services import Client as Database\n"
        "import services as svc\n"
        "Database(config).fetch()\n"
        "svc.Client(config).applications.logs(name)\n"
        "client = Database(config)\n"
    )

    # Check both diagnostic locations and the suggested fixes.
    findings = [finding for finding in check_file(path) if finding.code == "SLOP009"]
    assert [finding.line for finding in findings] == [3, 4, 5]
    assert "assign the Client instance to a name" in findings[0].message
    assert "across multiple lines" in findings[2].message


def test_relative_imports(tmp_path: Path) -> None:
    """Resolve direct class exports from a sibling package module."""
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "services.py").write_text("class Client: pass\n")
    path = tmp_path / "consumer.py"
    path.write_text("from .services import Client as Database\nDatabase().fetch()\n")
    assert [finding.code for finding in check_file(path) if finding.code == "SLOP009"] == ["SLOP009"]


def test_rebound_imported_classes_are_ignored(tmp_path: Path) -> None:
    """Do not infer constructors from exports replaced by a factory."""
    (tmp_path / "services.py").write_text("class Client: pass\nClient = factory\n")
    path = tmp_path / "consumer.py"
    path.write_text("from services import Client\nClient(config).fetch()\n")
    assert [finding.code for finding in check_file(path) if finding.code == "SLOP009"] == []


def test_invalid_imported_source_is_ignored(tmp_path: Path) -> None:
    """An unparseable dependency leaves imported constructor identity unknown."""
    (tmp_path / "services.py").write_text("class Client:\n")
    path = tmp_path / "consumer.py"
    path.write_text("from services import Client\nClient(config).fetch()\n")
    assert [finding.code for finding in check_file(path) if finding.code == "SLOP009"] == []
