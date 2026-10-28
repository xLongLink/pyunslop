import sys
import pytest
from pathlib import Path
from pytest_mock import MockerFixture
from pyunslop.cli import main
from collections.abc import Callable


@pytest.fixture
def run_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Callable[..., tuple[int, str, str]]:
    """Run the native CLI in an isolated project and capture both output streams."""
    monkeypatch.chdir(tmp_path)

    def run(*arguments: str) -> tuple[int, str, str]:
        monkeypatch.setattr(sys, "argv", ["pyunslop", *arguments])
        result = main()
        captured = capsys.readouterr()
        return result, captured.out, captured.err

    return run


def test_warnings_exit_successfully_without_modifying_source(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Report findings without changing source bytes or the success exit status."""
    source = "#bad\n" + "x = 1\n" * 11
    source_file.write_text(source)
    result, stdout, stderr = run_cli()
    assert result == 0
    assert "warning: SLOP003" in stdout
    assert "warning: SLOP001" in stdout
    assert "2 warning(s)" in stderr
    assert source_file.read_text() == source


def test_cli_does_not_run_external_checks(
    source_file: Path, run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture
) -> None:
    """Leave unused imports and formatting to separately installed tools."""
    source = "import os\nvalue=1\n"
    source_file.write_text(source)
    run = mocker.patch("subprocess.run", side_effect=AssertionError("External checker invoked"))
    assert run_cli() == (0, "Checks passed.\n", "")
    run.assert_not_called()
    assert source_file.read_text() == source


def test_model_field_order_is_warning_only(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Preserve source and section boundaries when reporting field order."""
    source = (
        "from pydantic import BaseModel\n"
        "class Read(BaseModel):\n    description: str\n    id: int\n"
        "class Sections(BaseModel):\n    description: str\n\n    id: int\n"
    )
    source_file.write_text(source)
    result, stdout, stderr = run_cli()
    assert (result, stderr) == (0, "Found 1 warning(s).\n")
    assert "example.py:4:5: warning: SLOP017" in stdout
    assert source_file.read_text() == source


def test_invalid_source_is_skipped_and_scan_continues(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Continue inspecting valid files after encountering invalid syntax."""
    source_file.write_text("def broken(\n")
    other = source_file.with_name("other.py")
    other.write_text("#bad\n")
    result, stdout, stderr = run_cli()
    assert result == 0
    assert source_file.name not in stdout
    assert "warning: SLOP003" in stdout
    assert "1 warning(s)" in stderr


def test_clean_file(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Report success without warning output for clean native source."""
    source_file.write_text("x = 1\n")
    assert run_cli() == (0, "Checks passed.\n", "")


def test_recursively_scans_project_with_fixed_exclusions(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Inspect nested source while excluding virtual-environment dependencies."""
    for directory in ("nested", ".venv"):
        path = source_file.parent / directory
        path.mkdir()
        (path / "module.py").write_text("#bad\n")

    # Act: run against the project root, not an individually selected file.
    result, stdout, stderr = run_cli()
    assert result == 0
    assert "nested/module.py" in stdout
    assert ".venv" not in stdout
    assert "1 warning(s)" in stderr


def test_directory_scan_failure_is_an_operational_error(run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture) -> None:
    """Distinguish filesystem traversal failures from ordinary findings."""
    mocker.patch("pyunslop.cli.find_python_files", side_effect=PermissionError("cannot scan"))
    result, _, stderr = run_cli()
    assert result == 2
    assert "Could not scan project" in stderr


def test_query_findings_are_warnings(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Run all initial query checks without turning findings into failures."""
    source_file.write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "async def fetch(s: AsyncSession) -> list[User]:\n"
        "    rows = (await s.execute(stmt)).all()\n"
        "    result = await s.scalars(stmt)\n"
        "    users = list(result.all())\n"
        "    return list(result.all())\n"
    )
    result, stdout, _ = run_cli()
    assert result == 0
    for code in ("SLOP005", "SLOP006", "SLOP007"):
        assert f"warning: {code}" in stdout


# Configuration flags and explicit paths are all rejected by the fixed-preset CLI.
@pytest.mark.parametrize("arguments", [("--max-lines", "1"), ("--repo-policy",), ("example.py",)])
def test_arguments_and_configuration_flags_are_not_supported(
    run_cli: Callable[..., tuple[int, str, str]], arguments: tuple[str, ...]
) -> None:
    """Reject paths and obsolete configuration flags instead of accepting overrides."""
    result, _, stderr = run_cli(*arguments)
    assert result == 2
    assert "takes no arguments" in stderr


def test_absolute_paths_are_not_supported(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Reject absolute source paths as well as relative paths and flags."""
    result, _, stderr = run_cli(str(source_file))
    assert result == 2
    assert "takes no arguments" in stderr


def test_additional_rules_are_warning_only(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Combine query, domain-instance, and API warnings in one scan."""
    source_file.write_text(
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
    result, stdout, _ = run_cli()
    assert result == 0
    for code in ("SLOP008", "SLOP009", "SLOP010", "SLOP011", "SLOP012"):
        assert f"warning: {code}" in stdout


def test_repository_policy_is_always_enabled_and_warning_only(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Enable repository policies without requiring opt-in flags."""
    source_file.write_text('"""Module docs."""\nfrom src.errors import ConflictError\n')
    result, stdout, _ = run_cli()
    assert result == 0
    assert "warning: SLOP013" in stdout
    assert "warning: SLOP014" in stdout


def test_review_candidates_are_warning_only(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Keep review candidates advisory across multiple rule families."""
    source_file.write_text(
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
    result, stdout, _ = run_cli()
    assert result == 0
    for code in ("SLOP020", "SLOP021", "SLOP022", "SLOP025"):
        assert f"warning: {code}" in stdout


def test_single_use_constant_is_warning_only(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Report SLOP026 without changing source or failing the command."""
    source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
    source_file.write_text(source)
    result, stdout, _ = run_cli()
    assert result == 0
    assert "warning: SLOP026" in stdout
    assert source_file.read_text() == source
