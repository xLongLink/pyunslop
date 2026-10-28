import ast
import unittest
from tests.support import codes, check_patterns


class ParametrizationStateTests(unittest.TestCase):
    """Keep pytest collection-hook exemptions local to their source module."""

    def test_module_exemptions_do_not_leak(self) -> None:
        """A collection hook must not suppress findings in a subsequent module."""

        # Arrange
        test = "@pytest.mark.parametrize('value', [1])\ndef test_value(value): pass"
        exempt = ast.parse("import pytest\ndef pytest_generate_tests(metafunc): pass\n" + test)
        flagged = ast.parse("import pytest\n" + test)

        # Act
        before = check_patterns(exempt)
        findings = check_patterns(flagged)
        after = check_patterns(exempt)

        # Assert
        assert before == after == []
        assert [finding.code for finding in findings] == ["PY015"]


class ParametrizationTests(unittest.TestCase):
    """Distinguish redundant literal cases from meaningful collection behavior."""

    def test_single_literal_case(self) -> None:
        """Flag one literal case in list and tuple parametrization forms."""
        for values in ('["acme"]', '[("acme", 1)]', '("acme",)'):
            with self.subTest(values=values):
                source = f'import pytest\n@pytest.mark.parametrize("name", {values})\ndef test_name(name):\n    assert name\n'
                assert codes(source) == ["PY015"]

    def test_keyword_case_and_mark_alias(self) -> None:
        """Recognize imported mark aliases and keyword-style parametrization."""
        source = """
        from pytest import mark as testmark
        @testmark.parametrize(argnames="name", argvalues=["acme"])
        def test_name(name):
            assert name
        """
        assert codes(source) == ["PY015"]

    def test_fixture_collection_and_dynamic_cases_are_preserved(self) -> None:
        """Preserve indirect fixtures, IDs, marks, scopes, and dynamic or multiple cases."""
        for arguments in (
            '"name", ["acme"], indirect=True',
            '"name", ["acme"], ids=["contract-id"]',
            '"name", ["acme"], scope="module"',
            '"name", [pytest.param("acme", marks=pytest.mark.slow)]',
            '"name", cases',
            '"name", ["acme", "other"]',
        ):
            # Act / Assert: preserve fixture, collection, and dynamic-case exemptions.
            with self.subTest(arguments=arguments):
                source = f"import pytest\n@pytest.mark.parametrize({arguments})\ndef test_name(name):\n    assert name\n"
                assert codes(source) == []

    def test_request_fixture_is_preserved(self) -> None:
        """Retain parametrization when request may inspect collection metadata."""
        source = """
        import pytest
        @pytest.mark.parametrize("name", ["acme"])
        def test_name(name, request):
            assert request.node.callspec
        """
        assert codes(source) == []

    def test_collection_hook_is_preserved(self) -> None:
        """Preserve cases in modules whose collection hooks can depend on them."""
        source = """
        import pytest
        def pytest_collection_modifyitems(items):
            pass
        @pytest.mark.parametrize("name", ["acme"])
        def test_name(name):
            assert name
        """
        assert codes(source) == []
