import ast
import pytest
from tests.support import RunCLI, native_codes
from pyunslop.rules.constants import single_use_constants


@pytest.mark.parametrize("literal", ['"Ready"', "30", "-30", '(1, "ready", (-2, None))'])
def test_reports_single_use_function_constants(run_cli: RunCLI, literal: str) -> None:
    """Recognize immutable literal values read exactly once in their scope."""

    # Arrange
    source = f"def render():\n    LABEL = {literal}\n    return format_label(LABEL)\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP023"]
    assert "example.py:2:5: SLOP023" in result.stdout


def test_reports_private_module_constant(run_cli: RunCLI) -> None:
    """Locate the private binding rather than its later consumer."""

    # Arrange
    source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == ["SLOP023"]
    assert "example.py:1:1: SLOP023" in result.stdout


EXEMPTIONS = (
    pytest.param('def render():\n    return format_label("Ready")\n', id="inlined-literal"),
    pytest.param("TIMEOUT = 30\nconnect(TIMEOUT)\n", id="public-module-name"),
    pytest.param('_TIMEOUT = 30\n__all__ = ["_TIMEOUT"]\nconnect(_TIMEOUT)\n', id="explicit-export"),
    pytest.param("class Config:\n    _TIMEOUT = 30\n    value = _TIMEOUT\n", id="class-constant"),
    # Reuse, rebinding, annotations, and nonliteral values invalidate single-use inlining.
    pytest.param("def render():\n    VALUE = 30\n    return VALUE + VALUE\n", id="multiple-reads"),
    pytest.param("def render():\n    VALUE = 30\n    VALUE = 40\n    return VALUE\n", id="rebinding"),
    pytest.param("def render():\n    VALUE: int = 30\n    return VALUE\n", id="annotation"),
    pytest.param("def render():\n    VALUE = [1]\n    return VALUE\n", id="mutable-value"),
    pytest.param("def render():\n    VALUE = make_value()\n    return VALUE\n", id="computed-value"),
    # Nested scopes and namespace introspection can observe otherwise hidden reads.
    pytest.param("def render():\n    VALUE = 30\n    def later():\n        return VALUE\n    return later\n", id="nested-reference"),
    pytest.param("def render():\n    VALUE = 30\n    return [VALUE for item in items]\n", id="comprehension-reference"),
    pytest.param("def render():\n    VALUE = 30\n    snapshot = locals()\n    return VALUE, snapshot\n", id="dynamic-namespace-access"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_contracts_mutability_and_scope_boundaries(run_cli: RunCLI, source: str) -> None:
    """Avoid inlining names when usage, identity, or visibility is uncertain."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


@pytest.mark.parametrize("source", ["pass\n", "TIMEOUT = 30\nconnect(TIMEOUT)\n", "def render():\n    return 30\n"])
def test_candidate_free_scopes_skip_reference_analysis(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    """Avoid traversing scopes that cannot produce a constant finding."""
    tree = ast.parse(source)
    scope = tree.body[0] if isinstance(tree.body[0], ast.FunctionDef) else tree

    def unexpected_walk(_node: ast.AST) -> None:
        pytest.fail("candidate-free scopes must not walk references")

    # Act
    with monkeypatch.context() as patch:
        patch.setattr(ast, "walk", unexpected_walk)
        findings = single_use_constants(scope)

    # Assert
    assert findings == []
