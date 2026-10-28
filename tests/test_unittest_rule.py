import ast
import pytest
from pathlib import Path
from pyunslop import check_file
from test_support import check_patterns


@pytest.mark.parametrize(
    "source",
    [
        "import unittest",
        "import unittest as ut",
        "import unittest.mock as mock",
        "from unittest import TestCase as Case",
        "from unittest.mock import patch, Mock",
        "from unittest import *",
        # Imports inside tests follow the same policy as module-level imports.
        "def test_example():\n    import unittest",
    ],
)
def test_unittest_imports(source: str) -> None:
    """Recommend pytest once per unittest import, regardless of alias or scope."""
    findings = check_patterns(ast.parse(source))
    assert [(finding.code, finding.message) for finding in findings] == [("PY016", "use pytest instead of unittest")]


@pytest.mark.parametrize(
    "source",
    [
        "import pytest",
        "import unittest_helper",
        "from unittest_helpers import TestCase",
        # Relative imports may refer to project-local modules.
        "from .unittest import TestCase",
        "from . import unittest",
        # An attribute imported from another module has unknown provenance.
        "from helpers import unittest",
        # Source text mentioning unittest is not an import.
        "text = 'import unittest'",
        "# import unittest",
    ],
)
def test_unrelated_and_relative_imports(source: str) -> None:
    """Do not guess provenance from names, strings, comments, or relative imports."""
    assert check_patterns(ast.parse(source)) == []


def test_unittest_warning_locations(tmp_path: Path) -> None:
    """Expose each offending import's one-based location through the public API."""
    path = tmp_path / "example.py"
    path.write_text("import os, unittest as ut\nfrom unittest.mock import Mock, patch\n")
    warnings = [warning for warning in check_file(path) if warning.code == "PY016"]
    assert [(warning.line, warning.column) for warning in warnings] == [(1, 12), (2, 1)]
