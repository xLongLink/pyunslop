import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pyunslop.cli import main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "example.py"
        previous = Path.cwd()
        os.chdir(self.temporary.name)
        self.addCleanup(os.chdir, previous)
        ruff = mock.patch("pyunslop.cli.check_ruff", return_value=[])
        ruff.start()
        self.addCleanup(ruff.stop)

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with mock.patch.object(sys, "argv", ["pyunslop", *arguments]):
                result = main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_warnings_exit_successfully_without_modifying_source(self) -> None:
        source = "#bad\n" + "x = 1\n" * 11
        self.path.write_text(source)
        result, stdout, stderr = self.run_cli()
        self.assertEqual(result, 0)
        self.assertIn("warning: CM003", stdout)
        self.assertIn("warning: CM001", stdout)
        self.assertIn("2 warning(s)", stderr)
        self.assertEqual(self.path.read_text(), source)

    def test_invalid_source_is_skipped_and_scan_continues(self) -> None:
        self.path.write_text("def broken(\n")
        other = self.path.with_name("other.py")
        other.write_text("#bad\n")
        result, stdout, stderr = self.run_cli()
        self.assertEqual(result, 0)
        self.assertNotIn(self.path.name, stdout)
        self.assertIn("warning: CM003", stdout)
        self.assertIn("1 warning(s)", stderr)

    def test_clean_file(self) -> None:
        self.path.write_text("x = 1\n")
        self.assertEqual(self.run_cli(), (0, "Checks passed.\n", ""))

    def test_recursively_scans_project_with_fixed_exclusions(self) -> None:
        for directory in ("nested", ".venv"):
            path = self.path.parent / directory
            path.mkdir()
            (path / "module.py").write_text("#bad\n")
        result, stdout, stderr = self.run_cli()
        self.assertEqual(result, 0)
        self.assertIn("nested/module.py", stdout)
        self.assertNotIn(".venv", stdout)
        self.assertIn("1 warning(s)", stderr)

    def test_directory_scan_failure_is_an_operational_error(self) -> None:
        with mock.patch("pyunslop.cli.find_python_files", side_effect=PermissionError("cannot scan")):
            result, _, stderr = self.run_cli()
        self.assertEqual(result, 2)
        self.assertIn("Could not scan project", stderr)

    def test_query_findings_are_warnings(self) -> None:
        self.path.write_text(
            "from sqlalchemy.ext.asyncio import AsyncSession\n"
            "async def fetch(s: AsyncSession) -> list[User]:\n"
            "    rows = (await s.execute(stmt)).all()\n"
            "    result = await s.scalars(stmt)\n"
            "    users = list(result.all())\n"
            "    return list(result.all())\n"
        )
        result, stdout, _ = self.run_cli()
        self.assertEqual(result, 0)
        for code in ("PY001", "PY002", "PY003"):
            self.assertIn(f"warning: {code}", stdout)

    def test_arguments_and_configuration_flags_are_not_supported(self) -> None:
        for arguments in (("--max-lines", "1"), ("--repo-policy",), (str(self.path),)):
            with self.subTest(arguments=arguments):
                result, _, stderr = self.run_cli(*arguments)
                self.assertEqual(result, 2)
                self.assertIn("takes no arguments", stderr)

    def test_additional_rules_are_warning_only(self) -> None:
        self.path.write_text(
            "from fastapi import FastAPI\n"
            "from sqlmodel import col\n"
            "from sqlalchemy.ext.asyncio import AsyncSession\n"
            "app = FastAPI()\n"
            "@app.get('/users')\n"
            "async def users(s: AsyncSession):\n"
            "    result = await s.execute(stmt)\n"
            "    for row in result.all():\n"
            "        consume(row)\n"
            "    expression = col(User.id).in_([item.id for item in items])\n"
            "    usage = await Postgres(host).usage()\n"
            "    return {'success': True, 'data': users}\n"
        )
        result, stdout, _ = self.run_cli()
        self.assertEqual(result, 0)
        for code in ("PY004", "PY005", "PY006", "PY009", "PY010"):
            self.assertIn(f"warning: {code}", stdout)

    def test_repository_policy_is_always_enabled_and_warning_only(self) -> None:
        self.path.write_text('"""Module docs."""\nfrom src.errors import ConflictError\n')
        result, stdout, _ = self.run_cli()
        self.assertEqual(result, 0)
        self.assertIn("warning: PY013", stdout)
        self.assertIn("warning: PY014", stdout)

    def test_review_candidates_are_warning_only(self) -> None:
        self.path.write_text(
            "from sqlalchemy.ext.asyncio import AsyncSession\n"
            "async def save(s: AsyncSession, item):\n"
            "    await s.commit()\n"
            "    await s.refresh(item)\n"
            "async def fetch(s: AsyncSession):\n"
            "    result = await s.execute(stmt)\n"
            "    return result.scalars().one_or_none()\n"
            "async def exists(s: AsyncSession):\n"
            "    result = await s.scalars(stmt)\n"
            "    return bool(result.all())\n"
            "total = sum([invoice.amount for invoice in invoices])\n"
        )
        result, stdout, _ = self.run_cli()
        self.assertEqual(result, 0)
        for code in ("PY107", "PY108", "PY109", "PY113"):
            self.assertIn(f"warning: {code}", stdout)

    def test_single_use_constant_is_warning_only(self) -> None:
        """Report PY114 without changing source or failing the command."""
        source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
        self.path.write_text(source)
        result, stdout, _ = self.run_cli()
        assert result == 0
        assert "warning: PY114" in stdout
        assert self.path.read_text() == source

    def test_module_defaults_to_current_directory_and_ignores_werror(self) -> None:
        self.path.write_text("#bad\n")
        result = subprocess.run(
            [sys.executable, "-W", "error", "-m", "pyunslop"],
            cwd=self.temporary.name, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning: CM003", result.stdout)


if __name__ == "__main__":
    unittest.main()
