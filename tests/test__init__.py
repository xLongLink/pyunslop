import pyunslop
from pyunslop.checker import check_file
from pyunslop.discovery import find_python_files
from importlib.resources import files
from pyunslop.diagnostics import Warning as CheckWarning


def test_package_exposes_its_type_information() -> None:
    """Ship the PEP 561 marker used by downstream static type checkers."""
    assert files("pyunslop").joinpath("py.typed").is_file()


def test_public_api_exports_are_available() -> None:
    """Consumers can import the documented API directly from the package."""

    # Arrange
    expected = {"Warning", "check_file", "find_python_files"}

    # Act
    exported = set(pyunslop.__all__)

    # Assert
    assert exported == expected
    assert pyunslop.Warning is CheckWarning
    assert pyunslop.check_file is check_file
    assert pyunslop.find_python_files is find_python_files
