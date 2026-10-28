import ast
import tempfile
import unittest
from pathlib import Path
from pyunslop import check_file
from unittest import mock
from importlib import import_module
from pyunslop.rules import COMMENT_RULES, ast_rules
from pyunslop.analysis import check_patterns
from importlib.resources import files

RULE_CODES = frozenset(
    (
        "CM001 CM002 CM003 PY001 PY002 PY003 PY004 PY005 PY006 PY009 PY010 PY013 PY014 "
        "PY015 PY016 PY017 PY101 PY106 PY107 PY108 PY109 PY110 PY111 PY113 PY114"
    ).split()
)


class RuleLayoutTests(unittest.TestCase):
    """Keep each native rule implementation independently owned and registered."""

    def test_each_rule_has_its_own_module(self) -> None:
        """Require one code-named module per native rule."""
        modules = {path.name[:-3] for path in files("pyunslop.rules").iterdir() if path.name.endswith(".py") and path.name != "__init__.py"}
        assert modules == {code.lower() for code in RULE_CODES}
        for code in RULE_CODES:
            module = import_module(f"pyunslop.rules.{code.lower()}")
            assert module.CODE == code

    def test_every_native_rule_is_in_the_fixed_registry(self) -> None:
        """Prevent extracting a rule into an unused or duplicate implementation."""
        checks = [*COMMENT_RULES, *(check for checks in ast_rules().values() for check in checks)]
        modules = {check.__module__.rsplit(".", 1)[-1] for check in checks}
        assert modules == {code.lower() for code in RULE_CODES}
        assert all(check.__module__.startswith("pyunslop.rules.") for check in checks)

    def test_one_source_parse_feeds_all_native_rules(self) -> None:
        """Share source parsing instead of reparsing independently for every rule."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("from src.errors import ConflictError\n#bad\n")
            with mock.patch("pyunslop.checker.ast.parse", wraps=ast.parse) as parse:
                warnings = check_file(path)
        assert parse.call_count == 1
        assert {warning.code for warning in warnings} == {"PY013", "CM002", "CM003"}

    def test_analysis_state_is_not_shared_between_files(self) -> None:
        """Keep imported session provenance local to one analyzer invocation."""
        typed = ast.parse(
            "from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(s: AsyncSession):\n    return (await s.execute(stmt)).all()\n"
        )
        unknown = ast.parse("async def fetch(s):\n    return (await s.execute(stmt)).all()\n")
        assert [code for _, code, _ in check_patterns(typed)] == ["PY001"]
        assert check_patterns(unknown) == []
        assert [code for _, code, _ in check_patterns(typed)] == ["PY001"]
