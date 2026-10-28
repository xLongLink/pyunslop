import sys
import tempfile
import unittest
import subprocess
from pathlib import Path


class ModuleTests(unittest.TestCase):
    """Check the installed package's module entry point."""

    def setUp(self) -> None:
        """Create the working directory passed to the module subprocess."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "example.py"

    def test_module_defaults_to_current_directory_and_ignores_werror(self) -> None:
        """Support module execution without emitting promotable Python warnings."""
        self.path.write_text("#bad\n")
        result = subprocess.run(
            [sys.executable, "-W", "error", "-m", "pyunslop"], cwd=self.temporary.name, capture_output=True, text=True, check=False
        )

        # Assert: subprocess success must still include the expected advisory finding.
        assert result.returncode == 0, result.stderr
        assert "warning: CM003" in result.stdout
