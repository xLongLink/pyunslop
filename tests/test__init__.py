import pyunslop
from pathlib import Path
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


def test_test_modules_mirror_package_modules() -> None:
    """Every Python module has exactly one corresponding test module."""

    # Arrange
    tests = Path(__file__).resolve().parent
    source = tests.parent / "src" / "pyunslop"

    # Act
    expected = {
        path.relative_to(source).with_name(f"test{path.name}" if path.name.startswith("__") else f"test_{path.name}")
        for path in source.rglob("*.py")
    }
    actual = {path.relative_to(tests) for path in tests.rglob("test_*.py")}

    # Assert
    assert actual == expected
