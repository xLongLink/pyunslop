import ast
import textwrap
from pyunslop.source import Source
from pyunslop.rules.simplifications import check_simplifications


def test_all_syntax_rule_families_are_included_without_rewriting() -> None:
    """The syntax pipeline must retain every delegated rule family's findings."""

    # Arrange
    source = textwrap.dedent("""\
        _TIMEOUT = 30
        connect(_TIMEOUT)
        def _fetch(value):
            return fetch(value)
        class Organizations:
            def __init__(self, client):
                self._client = client
            def fetch(self):
                return self._client.fetch()
        usage = Postgres(host).usage()
        total = sum([item.amount for item in items])
        rows = [Row(first=(value := item), second=value) for item in items]
        """)
    tree = ast.parse(source)
    before = ast.dump(tree)

    # Act
    findings = check_simplifications(Source(source, tree))

    # Assert
    assert sorted(finding.code for finding in findings) == ["SLOP010", "SLOP019", "SLOP020", "SLOP023", "SLOP024", "SLOP026"]
    assert ast.dump(tree) == before
