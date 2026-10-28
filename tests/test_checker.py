import ast
import tempfile
import tokenize
import unittest
from pathlib import Path
from pyunslop import Warning as CheckWarning
from pyunslop import check_file
from unittest import mock
from tests.support import QUERY_IMPORTS


class CheckerTests(unittest.TestCase):
    """Check file-level rule orchestration and unreadable-source handling."""

    def setUp(self) -> None:
        """Create an isolated directory for source fixtures."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def check(self, source: str) -> list[CheckWarning]:
        """Write a fixture and return native warnings for its exact source."""
        path = self.root / "example.py"
        path.write_text(source, encoding="utf-8")
        return check_file(path)

    def test_noqa_cannot_hide_native_findings(self) -> None:
        """A suppression must not hide itself or another native policy warning."""
        warnings = self.check("from src.errors import ConflictError  # noqa: PY013, CM004\n")
        assert {warning.code for warning in warnings} == {"PY013", "CM004"}

    def test_invalid_source_is_skipped(self) -> None:
        """Skip source that cannot be parsed by the native checks."""
        assert self.check("def broken(\n") == []

    def test_missing_file_is_skipped(self) -> None:
        """Skip an individual file that disappears before inspection."""
        assert check_file(self.root / "missing.py") == []

    def test_invalid_encoding_is_skipped(self) -> None:
        """Skip undecodable source without raising an inspection error."""
        path = self.root / "encoded.py"
        path.write_bytes(b"\xff\n")
        assert check_file(path) == []

    def test_limit_cannot_be_overridden(self) -> None:
        """Reject per-call overrides of the fixed comment limit."""
        error: TypeError | None = None
        try:
            check_file(self.root / "example.py", max_lines=1)
        except TypeError as exc:
            error = exc
        assert error is not None

    def test_repository_policies_cannot_be_disabled(self) -> None:
        """Reject per-call attempts to disable repository policies."""
        error: TypeError | None = None
        try:
            check_file(self.root / "example.py", repo_policy=False)
        except TypeError as exc:
            error = exc
        assert error is not None


class AnalysisTests(unittest.TestCase):
    """Exercise analyzer boundaries and shared parsing through observable results."""

    def test_one_source_parse_feeds_all_native_rules(self) -> None:
        """Share parsing and tokenization across independent analyzers."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("from src.errors import ConflictError\n#bad\n")
            with (
                mock.patch("pyunslop.source.ast.parse", wraps=ast.parse) as parse,
                mock.patch("pyunslop.source.tokenize.generate_tokens", wraps=tokenize.generate_tokens) as tokens,
            ):
                warnings = check_file(path)

        # Multiple AST traversals must not repeat parsing or tokenization.
        assert parse.call_count == 1
        assert tokens.call_count == 1
        assert {warning.code for warning in warnings} == {"PY013", "CM002", "CM003"}

    def test_comment_and_ast_locations_use_one_based_columns(self) -> None:
        """Both native diagnostic sources share the public location convention."""
        source = "from src.errors import ConflictError\n#bad\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text(source)
            warnings = check_file(path)
        assert [(warning.line, warning.column, warning.code) for warning in warnings] == [(1, 1, "PY013"), (2, 1, "CM002"), (2, 1, "CM003")]


class QueryIntegrationTests(unittest.TestCase):
    """Check query-result provenance, contracts, and consumption patterns."""

    def test_warning_location_and_integration(self) -> None:
        """Preserve one-based query warning locations in the public file API."""
        source = QUERY_IMPORTS + "async def fetch(s: AsyncSession):\n    return (await s.execute(stmt)).all()\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "query.py"
            path.write_text(source)
            warnings = check_file(path)
        assert [(w.code, w.line, w.column) for w in warnings] == [("PY001", 4, 12)]
