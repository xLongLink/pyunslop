import io
import os
import sys
import tempfile
import unittest
import contextlib
from pathlib import Path
from unittest import mock
from pyunslop.cli import main


class CliTests(unittest.TestCase):
    """Check fixed command behavior independently of Ruff's integration tests."""

    def setUp(self) -> None:
        """Use a temporary project and isolate native warning counts."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "example.py"
        previous = Path.cwd()
        os.chdir(self.temporary.name)
        self.addCleanup(os.chdir, previous)

        # Real Ruff execution has separate integration coverage; keep native counts isolated.
        ruff = mock.patch("pyunslop.cli.check_ruff", return_value=[])
        ruff.start()
        self.addCleanup(ruff.stop)

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Capture the command's exit status and both output streams."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with mock.patch.object(sys, "argv", ["pyunslop", *arguments]):
                result = main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_warnings_exit_successfully_without_modifying_source(self) -> None:
        """Report findings without changing source bytes or the success exit status."""
        source = "#bad\n" + "x = 1\n" * 11
        self.path.write_text(source)
        result, stdout, stderr = self.run_cli()
        assert result == 0
        assert "warning: CM003" in stdout
        assert "warning: CM001" in stdout
        assert "2 warning(s)" in stderr
        assert self.path.read_text() == source

    def test_model_field_order_is_warning_only(self) -> None:
        """Preserve source and section boundaries when reporting field order."""
        source = (
            "from pydantic import BaseModel\n"
            "class Read(BaseModel):\n    description: str\n    id: int\n"
            "class Sections(BaseModel):\n    description: str\n\n    id: int\n"
        )
        self.path.write_text(source)
        result, stdout, stderr = self.run_cli()
        assert (result, stderr) == (0, "Found 1 warning(s).\n")
        assert "example.py:4:5: warning: PY017" in stdout
        assert self.path.read_text() == source

    def test_invalid_source_is_skipped_and_scan_continues(self) -> None:
        """Continue inspecting valid files after encountering invalid syntax."""
        self.path.write_text("def broken(\n")
        other = self.path.with_name("other.py")
        other.write_text("#bad\n")
        result, stdout, stderr = self.run_cli()
        assert result == 0
        assert self.path.name not in stdout
        assert "warning: CM003" in stdout
        assert "1 warning(s)" in stderr

    def test_clean_file(self) -> None:
        """Report success without warning output for clean native source."""
        self.path.write_text("x = 1\n")
        assert self.run_cli() == (0, "Checks passed.\n", "")

    def test_recursively_scans_project_with_fixed_exclusions(self) -> None:
        """Inspect nested source while excluding virtual-environment dependencies."""
        for directory in ("nested", ".venv"):
            path = self.path.parent / directory
            path.mkdir()
            (path / "module.py").write_text("#bad\n")

        # Act: run against the project root, not an individually selected file.
        result, stdout, stderr = self.run_cli()
        assert result == 0
        assert "nested/module.py" in stdout
        assert ".venv" not in stdout
        assert "1 warning(s)" in stderr

    def test_directory_scan_failure_is_an_operational_error(self) -> None:
        """Distinguish filesystem traversal failures from ordinary findings."""
        with mock.patch("pyunslop.cli.find_python_files", side_effect=PermissionError("cannot scan")):
            result, _, stderr = self.run_cli()
        assert result == 2
        assert "Could not scan project" in stderr

    def test_query_findings_are_warnings(self) -> None:
        """Run all initial query checks without turning findings into failures."""
        self.path.write_text(
            "from sqlalchemy.ext.asyncio import AsyncSession\n"
            "async def fetch(s: AsyncSession) -> list[User]:\n"
            "    rows = (await s.execute(stmt)).all()\n"
            "    result = await s.scalars(stmt)\n"
            "    users = list(result.all())\n"
            "    return list(result.all())\n"
        )
        result, stdout, _ = self.run_cli()
        assert result == 0
        for code in ("PY001", "PY002", "PY003"):
            assert f"warning: {code}" in stdout

    def test_arguments_and_configuration_flags_are_not_supported(self) -> None:
        """Reject paths and obsolete configuration flags instead of accepting overrides."""
        for arguments in (("--max-lines", "1"), ("--repo-policy",), (str(self.path),)):
            with self.subTest(arguments=arguments):
                result, _, stderr = self.run_cli(*arguments)
                assert result == 2
                assert "takes no arguments" in stderr

    def test_additional_rules_are_warning_only(self) -> None:
        """Combine query, domain-instance, and API warnings in one scan."""
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
        assert result == 0
        for code in ("PY004", "PY005", "PY006", "PY009", "PY010"):
            assert f"warning: {code}" in stdout

    def test_repository_policy_is_always_enabled_and_warning_only(self) -> None:
        """Enable repository policies without requiring opt-in flags."""
        self.path.write_text('"""Module docs."""\nfrom src.errors import ConflictError\n')
        result, stdout, _ = self.run_cli()
        assert result == 0
        assert "warning: PY013" in stdout
        assert "warning: PY014" in stdout

    def test_review_candidates_are_warning_only(self) -> None:
        """Keep review candidates advisory across multiple rule families."""
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
        assert result == 0
        for code in ("PY107", "PY108", "PY109", "PY113"):
            assert f"warning: {code}" in stdout

    def test_single_use_constant_is_warning_only(self) -> None:
        """Report PY114 without changing source or failing the command."""
        source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
        self.path.write_text(source)
        result, stdout, _ = self.run_cli()
        assert result == 0
        assert "warning: PY114" in stdout
        assert self.path.read_text() == source
