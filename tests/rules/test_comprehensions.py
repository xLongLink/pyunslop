import ast
import unittest
from tests.support import codes, check_patterns


class ComprehensionStateTests(unittest.TestCase):
    """Keep comprehension deduplication local to each analysis."""

    def test_deduplication_is_local_to_one_analysis(self) -> None:
        """Rechecking a nested comprehension must retain exactly one finding."""

        # Arrange
        tree = ast.parse("rows = [[Row(x=(value := item), y=value) for item in group] for group in groups]")

        # Act
        first = check_patterns(tree)
        second = check_patterns(tree)

        # Assert
        assert [finding.code for finding in first] == ["PY106"]
        assert second == first


class ComprehensionReviewTests(unittest.TestCase):
    """Check constructor-argument dependencies inside comprehension expressions."""

    def test_constructor_argument_dependency(self) -> None:
        """Detect a walrus value reused by a later constructor argument."""
        source = """
        rows = [Audit(deleted_at=(deleted_at := latest(member)),
                      updated_at=max(member.updated_at, deleted_at or member.updated_at))
                for member in members]
        """
        assert codes(source) == ["PY106"]

    def test_independent_binding_and_non_comprehension_are_allowed(self) -> None:
        """Allow independent walrus bindings and ordinary non-comprehension calls."""
        source = """
        rows = [Audit(deleted_at=(deleted_at := latest(member))) for member in members]
        row = Audit(deleted_at=(deleted_at := latest(member)), updated_at=deleted_at)
        """
        assert codes(source) == []

    def test_generator_constructor_dependency(self) -> None:
        """Apply constructor-dependency checks to generator expressions too."""
        assert codes("rows = (Audit(first=(value := source(item)), second=value) for item in items)") == ["PY106"]
