import ast
import pytest
import textwrap
from tests.support import codes, check_patterns

LITERAL_VALUES = ("30", "-30", "+2.5", '"ready"', 'b"ready"', "True", "None", '(1, "ready", (-2, None))')


EXPORTED_CONSTANTS = (
    "TIMEOUT = 30\nconnect(TIMEOUT)\n",
    "class Config:\n    _TIMEOUT = 30\n    value = _TIMEOUT\n",
    '_TIMEOUT = 30\n__all__ = ["_TIMEOUT"]\nconnect(_TIMEOUT)\n',
)


# Require uppercase names, one read, and immutable values before reviewing a binding.
NON_CANDIDATE_BODIES = (
    "value = 30\nreturn value",
    "VALUE = 30\nreturn 1",
    "VALUE = 30\nreturn VALUE + VALUE",
    "VALUE = [1]\nreturn VALUE",
    "VALUE = (1, [])\nreturn VALUE",
    "VALUE = {1}\nreturn VALUE",
    'VALUE = {"key": 1}\nreturn VALUE',
    # Calls and annotations can carry behavior beyond the literal value.
    "VALUE = make_value()\nreturn VALUE",
    "VALUE = 1 + 2\nreturn VALUE",
    "VALUE: int = 30\nreturn VALUE",
    "VALUE = OTHER = 30\nreturn VALUE",
    "VALUE, = (30,)\nreturn VALUE",
    # Textual order alone cannot prove a conditional definition runs first.
    "return VALUE\nVALUE = 30",
    "if enabled:\n    VALUE = 30\nreturn VALUE",
    "VALUE = 30  # type: int\nreturn VALUE",
)


# Reassignment, deletion, and binding constructs prevent a single-use conclusion.
REBOUND_CONSTANTS = (
    "VALUE = 30\nVALUE = 40\nreturn VALUE",
    "VALUE = 30\nVALUE += 1\nreturn VALUE",
    "VALUE = 30\ndel VALUE\nreturn VALUE",
    "VALUE = 30\nfor VALUE in items:\n    pass\nreturn VALUE",
    "VALUE = 30\nimport other as VALUE\nreturn VALUE",
    "VALUE = 30\ndef VALUE():\n    pass\nreturn VALUE",
    "VALUE = 30\nclass VALUE:\n    pass\nreturn VALUE",
    # Exception and pattern bindings are represented as strings in the AST.
    "VALUE = 30\ntry:\n    work()\nexcept Error as VALUE:\n    pass\nreturn VALUE",
    'VALUE = 30\nmatch item:\n    case {"key": VALUE}:\n        pass\nreturn VALUE',
    "VALUE = 30\nmatch item:\n    case {**VALUE}:\n        pass\nreturn VALUE",
    "global VALUE\nVALUE = 30\nreturn VALUE",
    "nonlocal VALUE\nVALUE = 30\nreturn VALUE",
    "VALUE = 30\nreturn (VALUE := 40)",
)


# Closures and comprehensions may capture or shadow the same name.
NESTED_REFERENCES = (
    "VALUE = 30\ndef inner():\n    return VALUE\nreturn inner()",
    "VALUE = 30\nreturn lambda: VALUE",
    "VALUE = 30\nreturn [VALUE for item in items]",
    "VALUE = 30\nreturn [VALUE for VALUE in items]",
    # Class bodies and nested parameter lists introduce distinct scopes too.
    "VALUE = 30\nclass Inner:\n    value = VALUE\nreturn Inner",
    "VALUE = 30\ndef inner(VALUE):\n    pass\nreturn VALUE",
)


@pytest.mark.parametrize("literal", LITERAL_VALUES)
def test_local_literals(literal: str) -> None:
    """Include signed numbers and recursively immutable tuples."""
    assert codes(f"def run():\n    VALUE = {literal}\n    return consume(VALUE)\n") == ["SLOP023"]


def test_private_module_constant_and_location() -> None:
    """Point the warning at the redundant binding."""
    source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
    findings = check_patterns(ast.parse(source))
    assert [(finding.line, finding.column, finding.code) for finding in findings] == [(1, 1, "SLOP023")]


def test_async_function() -> None:
    """Apply the same check to async function bodies."""
    assert codes("async def run():\n    TIMEOUT = 30\n    await connect(timeout=TIMEOUT)\n") == ["SLOP023"]


def test_same_line_statement_order() -> None:
    """Accept later semicolon statements but not reads before the binding."""
    assert codes("_TIMEOUT = 30; connect(timeout=_TIMEOUT)\n") == ["SLOP023"]
    assert codes("connect(timeout=_TIMEOUT); _TIMEOUT = 30\n") == []


def test_method_local_constant() -> None:
    """Distinguish method locals from class-level contracts."""
    source = "class Client:\n    def connect(self):\n        TIMEOUT = 30\n        return connect(timeout=TIMEOUT)\n"
    assert codes(source) == ["SLOP023"]


def test_independent_scopes() -> None:
    """Do not combine unrelated constants sharing a name."""
    source = """
    def first():
        VALUE = 1
        return VALUE
    def second():
        VALUE = 2
        return VALUE
    """
    assert codes(source) == ["SLOP023", "SLOP023"]


@pytest.mark.parametrize("source", EXPORTED_CONSTANTS)
def test_public_class_and_exported_constants_are_preserved(source: str) -> None:
    """Keep externally accessible and explicitly exported contracts."""
    assert codes(source) == []


@pytest.mark.parametrize("body", NON_CANDIDATE_BODIES)
def test_non_candidates(body: str) -> None:
    """Require a single unannotated literal binding before its use."""
    source = "def run():\n" + textwrap.indent(body, "    ")
    assert check_patterns(ast.parse(source, type_comments=True)) == []


@pytest.mark.parametrize("body", REBOUND_CONSTANTS)
def test_rebinding_and_ambiguous_bindings_are_preserved(body: str) -> None:
    """Count non-Name bindings as well as ordinary stores and deletes."""
    assert codes("def run():\n" + textwrap.indent(body, "    ")) == []


def test_parameter_bindings_are_preserved() -> None:
    """An incoming parameter is a prior binding even when it is reassigned."""
    assert codes("def run(VALUE):\n    VALUE = 30\n    return VALUE\n") == []


@pytest.mark.parametrize("body", NESTED_REFERENCES)
def test_nested_scopes_and_comprehensions_are_preserved(body: str) -> None:
    """Avoid guessing whether nested names capture or shadow the constant."""
    assert codes("def run():\n" + textwrap.indent(body, "    ")) == []


def test_module_constant_closures_are_preserved() -> None:
    """A reference in a nested function must retain its module-level constant."""
    assert codes("_VALUE = 30\ndef run():\n    return _VALUE\n") == []


def test_deep_nested_capture_preserves_only_captured_constant() -> None:
    """Keep a deeply captured constant without excluding unrelated candidates."""
    source = """
    def outer():
        CAPTURED = 30
        SINGLE = 40
        def middle():
            def inner():
                return [CAPTURED for item in items]
            return inner
        return SINGLE, middle
    """
    findings = check_patterns(ast.parse(textwrap.dedent(source)))
    assert [(finding.code, finding.line, finding.column) for finding in findings] == [("SLOP023", 4, 5)]


@pytest.mark.parametrize("call", ["locals()", "globals()", "vars()", 'eval("VALUE")', 'exec("VALUE = 40")'])
def test_dynamic_namespace_access_is_preserved(call: str) -> None:
    """Namespace introspection can observe otherwise invisible uses."""
    assert codes(f"def run():\n    VALUE = 30\n    {call}\n    return VALUE\n") == []
