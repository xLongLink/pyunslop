import ast
import pytest
from tests.support import codes, check_patterns


def test_module_exemptions_do_not_leak() -> None:
    """Earlier CLI help must not exempt a later ordinary module docstring."""

    # Arrange
    exempt = ast.parse('"""Help."""\nimport argparse\nparser = argparse.ArgumentParser(description=__doc__)')
    flagged = ast.parse('"""Not CLI help."""')

    # Act
    before = check_patterns(exempt)
    findings = check_patterns(flagged)
    after = check_patterns(exempt)

    # Assert
    assert before == after == []
    assert [finding.code for finding in findings] == ["SLOP012"]


def test_module_docstring_only() -> None:
    """Keep function docstrings outside the leading-module-docstring policy."""
    assert codes('def fn():\n    """Function docs."""\n    pass\n') == []


def test_cli_help_exemption() -> None:
    """Allow module documentation used explicitly as argparse help."""
    source = '''\
    """Command help."""
    from argparse import ArgumentParser as Parser
    parser = Parser(description=__doc__)
    '''
    assert codes(source) == []


def test_merely_referencing_doc_is_not_cli_help() -> None:
    """Require a recognized CLI-help use rather than any reference to __doc__."""
    source = '"""Module docs."""\nprint(__doc__)\n'
    assert codes(source) == ["SLOP012"]


@pytest.mark.parametrize("revises", ["", "abc123", "abc123, def456"])
@pytest.mark.parametrize("date", ["2026-10-28 12:34:56", "2026-10-28 12:34:56.123456"])
def test_alembic_revision_header_exemption(revises: str, date: str) -> None:
    """Allow generated headers for initial, ordinary, and merge revisions."""
    source = f'''\
    """Create accounts.

    Revision ID: abc789
    Revises: {revises}
    Create Date: {date}

    """
    '''
    assert codes(source) == []


# A date alone or an incomplete header must not bypass the policy.
@pytest.mark.parametrize(
    "header",
    [
        "2026-10-28 Create accounts.",
        "Create Date: 2026-10-28 12:34:56",
        "Revision ID: abc789\nRevises: abc123",
        "Revision ID: abc789\nRevises: abc123\nCreate Date: not a date",
        "Revision ID: \nRevises: abc123\nCreate Date: 2026-10-28 12:34:56",
    ],
)
def test_other_dated_docstrings_are_not_exempt(header: str) -> None:
    """Require a complete revision header rather than just a date."""
    assert codes(f'"""{header}"""') == ["SLOP012"]
