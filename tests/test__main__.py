import sys
import pytest
import subprocess
from pathlib import Path
from pytest_mock import MockerFixture
from collections.abc import Callable
from pyunslop.__main__ import main
from pyunslop.diagnostics import Warning as Diagnostic


@pytest.fixture
def run_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> Callable[..., tuple[int, str, str]]:
    """Run the native CLI in an isolated project and capture both output streams."""
    monkeypatch.chdir(tmp_path)
    mocker.patch("pyunslop.__main__.check_ruff", return_value=[])

    def run(*arguments: str) -> tuple[int, str, str]:
        monkeypatch.setattr(sys, "argv", ["pyunslop", *arguments])
        result = main()
        captured = capsys.readouterr()
        return result, captured.out, captured.err

    return run


def test_findings_fail_without_modifying_source(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Report lint failures without changing source bytes."""
    source = "# noqa\n" + "x = 1\n" * 11
    source_file.write_text(source)
    result, stdout, stderr = run_cli()

    # Findings fail the command without Python warning output or source edits.
    assert result == 1
    assert ": SLOP003" in stdout
    assert ": SLOP001" in stdout
    assert "Found 2 errors." in stdout
    assert stderr == ""
    assert source_file.read_text() == source


def test_cli_runs_ruff(source_file: Path, run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture) -> None:
    """Give Ruff findings the same output and status as native findings."""
    source = "import os\nvalue=1\n"
    source_file.write_text(source)
    run = mocker.patch("pyunslop.__main__.check_ruff", return_value=[Diagnostic(Path("example.py"), 1, 8, "F401", "unused import")])
    assert run_cli() == (1, "example.py:1:8: F401 unused import\nFound 1 error.\n", "")
    run.assert_called_once_with()
    assert source_file.read_text() == source


def test_ruff_failure_is_an_operational_error(run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture) -> None:
    """Fail when Ruff cannot complete instead of announcing success."""
    mocker.patch("pyunslop.__main__.check_ruff", side_effect=RuntimeError("Ruff failed"))
    result, stdout, stderr = run_cli()
    assert result == 2
    assert "Checks passed" not in stdout
    assert "Ruff failed" in stderr


def test_native_and_ruff_findings_share_sorted_report(
    source_file: Path, run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture
) -> None:
    """Count and order both rule families together without duplicate summaries."""
    source_file.write_text("value = 1\n\n# noqa\n")
    mocker.patch(
        "pyunslop.__main__.check_ruff", return_value=[Diagnostic(Path("example.py"), 1, 1, "unformatted", "File would be reformatted")]
    )
    result, stdout, stderr = run_cli()

    # Formatting and native findings contribute equally to the failure status.
    assert result == 1
    assert stderr == ""
    lines = stdout.splitlines()
    assert lines[0] == "example.py:1:1: unformatted File would be reformatted"
    assert ": SLOP003" in lines[1]
    assert lines[2:] == ["Found 2 errors."]


def test_module_defaults_to_current_directory_and_ignores_werror(tmp_path: Path, source_file: Path) -> None:
    """Support module execution without emitting promotable Python warnings."""
    source_file.write_text("# noqa\n")
    result = subprocess.run([sys.executable, "-W", "error", "-m", "pyunslop"], cwd=tmp_path, capture_output=True, text=True, check=False)

    # Python warning filters do not affect lint diagnostics or their status.
    assert result.returncode == 1, result.stderr
    assert ": SLOP003" in result.stdout


def test_model_field_order_fails(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Preserve source and section boundaries when reporting field order."""
    source = (
        "from pydantic import BaseModel\n"
        "class Read(BaseModel):\n    description: str\n    id: int\n"
        "class Sections(BaseModel):\n    description: str\n\n    id: int\n"
    )
    source_file.write_text(source)
    result, stdout, stderr = run_cli()

    # The diagnostic retains its original location and shares the lint summary.
    assert (result, stderr) == (1, "")
    assert "Found 1 error." in stdout
    assert "example.py:4:5: SLOP014" in stdout
    assert source_file.read_text() == source


def test_invalid_source_is_skipped_and_scan_continues(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Continue inspecting valid files after encountering invalid syntax."""
    source_file.write_text("def broken(\n")
    other = source_file.with_name("other.py")
    other.write_text("# noqa\n")
    result, stdout, stderr = run_cli()

    # The valid sibling is still checked after the native parser skips bad syntax.
    assert result == 1
    assert source_file.name not in stdout
    assert ": SLOP003" in stdout
    assert "Found 1 error." in stdout
    assert stderr == ""


def test_clean_file(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Report Ruff-style success for clean source."""
    source_file.write_text("x = 1\n")
    assert run_cli() == (0, "All checks passed!\n", "")


def test_recursively_scans_project_with_fixed_exclusions(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Inspect nested source while excluding virtual-environment dependencies."""
    for directory in ("nested", ".venv"):
        path = source_file.parent / directory
        path.mkdir()
        (path / "module.py").write_text("# noqa\n")

    # Act: run against the project root, not an individually selected file.
    result, stdout, stderr = run_cli()
    assert result == 1
    assert "nested/module.py" in stdout
    assert ".venv" not in stdout
    assert "Found 1 error." in stdout
    assert stderr == ""


def test_directory_scan_failure_is_an_operational_error(run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture) -> None:
    """Distinguish filesystem traversal failures from ordinary findings."""
    mocker.patch("pyunslop.__main__.find_python_files", side_effect=PermissionError("cannot scan"))
    result, _, stderr = run_cli()
    assert result == 2
    assert "Could not scan project" in stderr


def test_file_read_failure_is_an_operational_error(
    source_file: Path, run_cli: Callable[..., tuple[int, str, str]], mocker: MockerFixture
) -> None:
    """Return status two when a discovered file cannot be read."""
    source_file.write_text("value = 1\n")
    mocker.patch("pyunslop.checker.Source.read", side_effect=PermissionError("cannot read"))
    result, stdout, stderr = run_cli()
    assert result == 2
    assert "All checks passed!" not in stdout
    assert "cannot read" in stderr


def test_git_ignored_native_findings_are_not_reported(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Match Ruff's Git ignore semantics in the full native CLI scan."""
    subprocess.run(["git", "init", "--quiet"], check=True)
    source_file.write_text("# noqa\n")
    source_file.with_name(".gitignore").write_text("example.py\n")
    assert run_cli() == (0, "All checks passed!\n", "")


def test_query_findings_fail(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Run all initial query checks and fail on their findings."""
    source_file.write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "async def fetch(s: AsyncSession) -> list[User]:\n"
        "    rows = (await s.execute(stmt)).all()\n"
        "    result = await s.scalars(stmt)\n"
        "    users = list(result.all())\n"
        "    return list(result.all())\n"
    )
    result, stdout, _ = run_cli()
    assert result == 1
    for code in ("SLOP004", "SLOP005", "SLOP006"):
        assert f": {code}" in stdout


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


def test_additional_rules_fail(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Combine query, domain-instance, and API findings in one scan."""
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
    assert result == 1
    for code in ("SLOP007", "SLOP008", "SLOP009", "SLOP010", "SLOP011"):
        assert f": {code}" in stdout


def test_repository_policy_is_always_enabled(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Enable repository policies without requiring opt-in flags."""
    source_file.write_text('"""Module docs."""\n')
    result, stdout, _ = run_cli()
    assert result == 1
    assert ": SLOP012" in stdout


def test_review_candidates_fail(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Include review candidates in the lint failure status."""
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
        "total = tuple([invoice.amount for invoice in invoices])\n"
    )
    result, stdout, _ = run_cli()
    assert result == 1
    for code in ("SLOP017", "SLOP018", "SLOP019", "SLOP022"):
        assert f": {code}" in stdout


def test_single_use_constant_fails(source_file: Path, run_cli: Callable[..., tuple[int, str, str]]) -> None:
    """Report SLOP023 as a failure without changing source."""
    source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
    source_file.write_text(source)
    result, stdout, _ = run_cli()
    assert result == 1
    assert ": SLOP023" in stdout
    assert source_file.read_text() == source
