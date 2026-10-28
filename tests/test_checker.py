import ast
import pytest
import tokenize
from pathlib import Path
from pyunslop import Warning as CheckWarning
from pyunslop import check_file
from pytest_mock import MockerFixture
from tests.support import QUERY_IMPORTS
from collections.abc import Callable


def test_noqa_cannot_hide_native_findings(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """A suppression must not hide itself or another native policy warning."""
    warnings = check_source('"""Module docs."""  # noqa: SLOP014, SLOP004\n')
    assert {warning.code for warning in warnings} == {"SLOP014", "SLOP004"}


def test_invalid_source_is_skipped(check_source: Callable[[str], list[CheckWarning]]) -> None:
    """Skip source that cannot be parsed by the native checks."""
    assert check_source("def broken(\n") == []


def test_missing_file_is_skipped(tmp_path: Path) -> None:
    """Skip an individual file that disappears before inspection."""
    assert check_file(tmp_path / "missing.py") == []


def test_invalid_encoding_is_skipped(tmp_path: Path) -> None:
    """Skip undecodable source without raising an inspection error."""
    path = tmp_path / "encoded.py"
    path.write_bytes(b"\xff\n")
    assert check_file(path) == []


def test_limit_cannot_be_overridden(tmp_path: Path) -> None:
    """Reject per-call overrides of the fixed comment limit."""
    with pytest.raises(TypeError, match="max_lines"):
        check_file(tmp_path / "example.py", max_lines=1)


def test_repository_policies_cannot_be_disabled(tmp_path: Path) -> None:
    """Reject per-call attempts to disable repository policies."""
    with pytest.raises(TypeError, match="repo_policy"):
        check_file(tmp_path / "example.py", repo_policy=False)


def test_one_source_parse_feeds_all_native_rules(source_file: Path, mocker: MockerFixture) -> None:
    """Share parsing and tokenization across independent analyzers."""
    source_file.write_text('"""Module docs."""\n#bad\n')
    parse = mocker.patch("pyunslop.source.ast.parse", wraps=ast.parse)
    tokens = mocker.patch("pyunslop.source.tokenize.generate_tokens", wraps=tokenize.generate_tokens)
    warnings = check_file(source_file)

    # Multiple AST traversals must not repeat parsing or tokenization.
    assert parse.call_count == 1
    assert tokens.call_count == 1
    assert {warning.code for warning in warnings} == {"SLOP014", "SLOP002", "SLOP003"}


def test_comment_and_ast_locations_use_one_based_columns(source_file: Path) -> None:
    """Both native diagnostic sources share the public location convention."""
    source = '"""Module docs."""\n#bad\n'
    source_file.write_text(source)
    warnings = check_file(source_file)
    assert [(warning.line, warning.column, warning.code) for warning in warnings] == [(1, 1, "SLOP014"), (2, 1, "SLOP002"), (2, 1, "SLOP003")]


def test_warning_location_and_integration(tmp_path: Path) -> None:
    """Preserve one-based query warning locations in the public file API."""
    source = QUERY_IMPORTS + "async def fetch(s: AsyncSession):\n    return (await s.execute(stmt)).all()\n"
    path = tmp_path / "query.py"
    path.write_text(source)
    warnings = check_file(path)
    assert [(w.code, w.line, w.column) for w in warnings] == [("SLOP005", 4, 12)]
