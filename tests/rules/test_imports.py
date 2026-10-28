import ast
import tempfile
import unittest
from pathlib import Path
from pyunslop import check_file
from tests.support import codes, check_patterns


class UnittestImportTests(unittest.TestCase):
    """Check unittest import detection without requiring pytest to run the suite."""

    def test_unittest_imports(self) -> None:
        """Recommend pytest once per unittest import, regardless of alias or scope."""

        # Arrange
        sources = (
            "import unittest",
            "import unittest as ut",
            "import unittest.mock as mock",
            "from unittest import TestCase as Case",
            "from unittest.mock import patch, Mock",
            "from unittest import *",
            # Imports inside tests follow the same policy as module-level imports.
            "def test_example():\n    import unittest",
        )
        for source in sources:
            with self.subTest(source=source):
                # Act
                findings = check_patterns(ast.parse(source))

                # Assert
                assert [(finding.code, finding.message) for finding in findings] == [("PY016", "use pytest instead of unittest")]

    def test_unrelated_and_relative_imports(self) -> None:
        """Ignore unknown provenance, strings, comments, and relative imports."""

        # Arrange
        sources = (
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
        for source in sources:
            with self.subTest(source=source):
                # Act
                findings = check_patterns(ast.parse(source))

                # Assert
                assert findings == []

    def test_unittest_warning_locations(self) -> None:
        """Expose each offending import's one-based location through the public API."""

        # Arrange
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("import os, unittest as ut\nfrom unittest.mock import Mock, patch\n")

            # Act
            warnings = [warning for warning in check_file(path) if warning.code == "PY016"]

        # Assert
        assert [(warning.line, warning.column) for warning in warnings] == [(1, 12), (2, 1)]


class RetiredImportTests(unittest.TestCase):
    """Check the fixed import and module-documentation policies."""

    def test_retired_import_forms(self) -> None:
        """Reject absolute imports of retired wrappers and their submodules."""
        for source in (
            "from src.errors import ConflictError",
            "import src.errors as errors",
            "from src import errors",
            "import src.errors.http",
            "from src.errors.http import ConflictError",
        ):
            # Act / Assert: each retired absolute import form must be rejected.
            with self.subTest(source=source):
                assert codes(source) == ["PY013"]

    def test_unrelated_imports_and_http_exception_are_allowed(self) -> None:
        """Allow unrelated error modules and direct FastAPI HTTP exceptions."""
        assert codes("from other.errors import ConflictError\nfrom fastapi import HTTPException") == []
