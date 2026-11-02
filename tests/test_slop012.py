import pytest
from tests.support import RunCLI, native_codes

CANDIDATES = (
    pytest.param('"""User lookup utilities."""\ndef find_user(user_id):\n    return users.get(user_id)\n', id="leading-module-docstring"),
    pytest.param('"""Module docs."""\nprint(__doc__)\n', id="unrelated-doc-reference"),
    pytest.param('"""Create Date: 2026-10-28 12:34:56"""\n', id="date-only"),
    pytest.param('"""Revision ID: abc789\nRevises: abc123\nCreate Date: not a date\n"""\n', id="invalid-migration-header"),
)


@pytest.mark.parametrize("source", CANDIDATES)
def test_rejects_leading_docstrings_without_a_documented_use(run_cli: RunCLI, source: str) -> None:
    """Require recognized CLI help or a complete generated migration header."""

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP012"]


EXEMPTIONS = (
    pytest.param(
        'def find_user(user_id):\n    """Look up a user by identifier."""\n    return users.get(user_id)\n', id="function-docstring"
    ),
    pytest.param('class Users:\n    """Store user records."""\n', id="class-docstring"),
    # CLI APIs must explicitly consume the module docstring as help.
    pytest.param(
        '"""Command help."""\nfrom argparse import ArgumentParser as Parser\nparser = Parser(description=__doc__)\n',
        id="argparse-help-alias",
    ),
    pytest.param('"""Command help."""\nimport click\n@click.command(help=__doc__)\ndef command():\n    pass\n', id="click-help"),
    pytest.param('"""Command help."""\nimport typer\napp = typer.Typer(help=__doc__)\n', id="typer-help"),
    # Initial and merge migrations both carry complete generated headers.
    pytest.param(
        '"""Create accounts.\n\nRevision ID: abc789\nRevises: \nCreate Date: 2026-10-28 12:34:56\n\n"""\n', id="initial-migration"
    ),
    pytest.param(
        '"""Create accounts.\n\nRevision ID: abc789\nRevises: abc123, def456\nCreate Date: 2026-10-28 12:34:56.123456\n\n"""\n',
        id="merge-migration",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_nested_docs_cli_help_and_migrations(run_cli: RunCLI, source: str) -> None:
    """Allow the uses explicitly exempted by the repository policy."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


def test_cli_help_exemption_does_not_leak_between_files(run_cli: RunCLI) -> None:
    """Scan real sibling modules with independent docstring policy state."""

    # Arrange
    sources = {
        "a_help.py": '"""Help."""\nimport argparse\nparser = argparse.ArgumentParser(description=__doc__)\n',
        "b_module.py": '"""Not CLI help."""\n',
    }

    # Act
    result = run_cli(sources)

    # Assert
    assert native_codes(result) == ["SLOP012"]
    assert "b_module.py:1:1: SLOP012" in result.stdout


@pytest.mark.parametrize(
    ("imported", "decorator", "definition"),
    [("import click", "click.command", "def"), ("from click import group as click", "click", "async def")],
)
def test_click_help_decorators_use_the_enclosing_scope(run_cli: RunCLI, imported: str, decorator: str, definition: str) -> None:
    """Resolve synchronous and asynchronous decorators before parameter shadowing."""

    # Arrange
    source = f'"""Command help."""\n{imported}\n@{decorator}(help=__doc__)\n{definition} command(click):\n    pass\n'

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
