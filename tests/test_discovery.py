import tempfile
import unittest
from pathlib import Path
from pyunslop import find_python_files


class DiscoveryTests(unittest.TestCase):
    """Check file discovery, generated-directory exclusions, and deduplication."""

    def setUp(self) -> None:
        """Create an isolated directory for source fixtures."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_discovery_excludes_generated_files_and_deduplicates(self) -> None:
        """Skip generated directories unless an explicit file path requests them."""
        source = self.root / "source.py"
        source.touch()
        (self.root / "notes.txt").touch()
        excluded = self.root / ".venv"
        excluded.mkdir()
        hidden_source = excluded / "dependency.py"
        hidden_source.touch()

        # Act / Assert: overlapping project paths must not duplicate source files.
        assert list(find_python_files([self.root, source])) == [source]
        assert list(find_python_files([hidden_source])) == [hidden_source]

    def test_missing_discovery_path_raises(self) -> None:
        """Report a missing discovery root rather than silently skipping it."""
        error: FileNotFoundError | None = None
        try:
            list(find_python_files([self.root / "missing"]))
        except FileNotFoundError as exc:
            error = exc
        assert error is not None
