import ast
import textwrap
import unittest
from tests.support import codes, check_patterns


class SingleUseConstantTests(unittest.TestCase):
    """Check literal candidates and scope/export safeguards."""

    def test_local_literals(self) -> None:
        """Include signed numbers and recursively immutable tuples."""
        for literal in ("30", "-30", "+2.5", '"ready"', 'b"ready"', "True", "None", '(1, "ready", (-2, None))'):
            with self.subTest(literal=literal):
                assert codes(f"def run():\n    VALUE = {literal}\n    return consume(VALUE)\n") == ["PY114"]

    def test_private_module_constant_and_location(self) -> None:
        """Point the warning at the redundant binding."""
        source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
        findings = check_patterns(ast.parse(source))
        assert [(finding.line, finding.column, finding.code) for finding in findings] == [(1, 1, "PY114")]

    def test_async_function(self) -> None:
        """Apply the same check to async function bodies."""
        assert codes("async def run():\n    TIMEOUT = 30\n    await connect(timeout=TIMEOUT)\n") == ["PY114"]

    def test_same_line_statement_order(self) -> None:
        """Accept later semicolon statements but not reads before the binding."""
        assert codes("_TIMEOUT = 30; connect(timeout=_TIMEOUT)\n") == ["PY114"]
        assert codes("connect(timeout=_TIMEOUT); _TIMEOUT = 30\n") == []

    def test_method_local_constant(self) -> None:
        """Distinguish method locals from class-level contracts."""
        source = "class Client:\n    def connect(self):\n        TIMEOUT = 30\n        return connect(timeout=TIMEOUT)\n"
        assert codes(source) == ["PY114"]

    def test_independent_scopes(self) -> None:
        """Do not combine unrelated constants sharing a name."""
        source = """
        def first():
            VALUE = 1
            return VALUE
        def second():
            VALUE = 2
            return VALUE
        """
        assert codes(source) == ["PY114", "PY114"]

    def test_public_class_and_exported_constants_are_preserved(self) -> None:
        """Keep externally accessible and explicitly exported contracts."""
        for source in (
            "TIMEOUT = 30\nconnect(TIMEOUT)\n",
            "class Config:\n    _TIMEOUT = 30\n    value = _TIMEOUT\n",
            '_TIMEOUT = 30\n__all__ = ["_TIMEOUT"]\nconnect(_TIMEOUT)\n',
        ):
            with self.subTest(source=source):
                assert codes(source) == []

    def test_non_candidates(self) -> None:
        """Require a single unannotated literal binding before its use."""
        for body in (
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
        ):
            with self.subTest(body=body):
                source = "def run():\n" + textwrap.indent(body, "    ")
                assert check_patterns(ast.parse(source, type_comments=True)) == []

    def test_rebinding_and_ambiguous_bindings_are_preserved(self) -> None:
        """Count non-Name bindings as well as ordinary stores and deletes."""
        for body in (
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
        ):
            with self.subTest(body=body):
                assert codes("def run():\n" + textwrap.indent(body, "    ")) == []
        assert codes("def run(VALUE):\n    VALUE = 30\n    return VALUE\n") == []

    def test_nested_scopes_and_comprehensions_are_preserved(self) -> None:
        """Avoid guessing whether nested names capture or shadow the constant."""
        for body in (
            "VALUE = 30\ndef inner():\n    return VALUE\nreturn inner()",
            "VALUE = 30\nreturn lambda: VALUE",
            "VALUE = 30\nreturn [VALUE for item in items]",
            "VALUE = 30\nreturn [VALUE for VALUE in items]",
            # Class bodies and nested parameter lists introduce distinct scopes too.
            "VALUE = 30\nclass Inner:\n    value = VALUE\nreturn Inner",
            "VALUE = 30\ndef inner(VALUE):\n    pass\nreturn VALUE",
        ):
            with self.subTest(body=body):
                assert codes("def run():\n" + textwrap.indent(body, "    ")) == []
        assert codes("_VALUE = 30\ndef run():\n    return _VALUE\n") == []

    def test_dynamic_namespace_access_is_preserved(self) -> None:
        """Namespace introspection can observe otherwise invisible uses."""
        for call in ("locals()", "globals()", "vars()", 'eval("VALUE")', 'exec("VALUE = 40")'):
            with self.subTest(call=call):
                assert codes(f"def run():\n    VALUE = 30\n    {call}\n    return VALUE\n") == []
