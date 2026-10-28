import ast
import pytest
from pathlib import Path
from pyunslop import check_file
from tests.support import codes, check_patterns

UNITTEST_IMPORTS = (
    "import unittest",
    "import unittest as ut",
    "import unittest.mock as mock",
    "from unittest import TestCase as Case",
    "from unittest.mock import patch, Mock",
    "from unittest import *",
    # Imports inside tests follow the same policy as module-level imports.
    "def test_example():\n    import unittest",
)


UNRELATED_IMPORTS = (
    "import pytest",
    "import unittest_helper",
    "from unittest_helpers import TestCase",
    # Relative imports may refer to project-local modules.
    "from .unittest import TestCase",
    "from . import unittest",
    "from helpers import unittest",
    "text = 'import unittest'",
    "# import unittest",
)


# The retired-wrapper policy applies equally to modules, submodules, and symbols.
RETIRED_IMPORTS = (
    "from src.errors import ConflictError",
    "import src.errors as errors",
    "from src import errors",
    "import src.errors.http",
    "from src.errors.http import ConflictError",
)


@pytest.mark.parametrize("source", UNITTEST_IMPORTS)
def test_unittest_imports(source: str) -> None:
    """Recommend pytest once per unittest import, regardless of alias or scope."""

    # Act
    findings = check_patterns(ast.parse(source))

    # Assert
    assert [(finding.code, finding.message) for finding in findings] == [("PY016", "use pytest instead of unittest")]


@pytest.mark.parametrize("source", UNRELATED_IMPORTS)
def test_unrelated_and_relative_imports(source: str) -> None:
    """Ignore unknown provenance, strings, comments, and relative imports."""

    # Act
    findings = check_patterns(ast.parse(source))

    # Assert
    assert findings == []


def test_unittest_warning_locations(source_file: Path) -> None:
    """Expose each offending import's one-based location through the public API."""

    # Arrange
    source_file.write_text("import os, unittest as ut\nfrom unittest.mock import Mock, patch\n")

    # Act
    warnings = [warning for warning in check_file(source_file) if warning.code == "PY016"]

    # Assert
    assert [(warning.line, warning.column) for warning in warnings] == [(1, 12), (2, 1)]


@pytest.mark.parametrize("source", RETIRED_IMPORTS)
def test_retired_import_forms(source: str) -> None:
    """Reject absolute imports of retired wrappers and their submodules."""
    assert codes(source) == ["PY013"]


def test_unrelated_imports_and_http_exception_are_allowed() -> None:
    """Allow unrelated error modules and direct FastAPI HTTP exceptions."""
    assert codes("from other.errors import ConflictError\nfrom fastapi import HTTPException") == []
