import ast
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
    assert [finding.code for finding in findings] == ["SLOP013"]


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
    assert codes(source) == ["SLOP013"]
