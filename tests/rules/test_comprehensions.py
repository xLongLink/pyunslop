import ast
from tests.support import codes, check_patterns
from pyunslop.rules.comprehensions import argument_dependencies


def test_deduplication_is_local_to_one_analysis() -> None:
    """Rechecking a nested comprehension must retain exactly one finding."""

    # Arrange
    tree = ast.parse("rows = [[Row(x=(value := item), y=value) for item in group] for group in groups]")

    # Act
    first = check_patterns(tree)
    second = check_patterns(tree)

    # Assert
    assert [finding.code for finding in first] == ["SLOP016"]
    assert second == first


def test_constructor_argument_dependency() -> None:
    """Detect a walrus value reused by a later constructor argument."""
    source = """
    rows = [Audit(deleted_at=(deleted_at := latest(member)),
                  updated_at=max(member.updated_at, deleted_at or member.updated_at))
            for member in members]
    """
    assert codes(source) == ["SLOP016"]


def test_independent_binding_and_non_comprehension_are_allowed() -> None:
    """Allow independent walrus bindings and ordinary non-comprehension calls."""
    source = """
    rows = [Audit(deleted_at=(deleted_at := latest(member))) for member in members]
    row = Audit(deleted_at=(deleted_at := latest(member)), updated_at=deleted_at)
    """
    assert codes(source) == []


def test_generator_constructor_dependency() -> None:
    """Apply constructor-dependency checks to generator expressions too."""
    assert codes("rows = (Audit(first=(value := source(item)), second=value) for item in items)") == ["SLOP016"]


def test_argument_dependencies_preserve_binding_order() -> None:
    """Keep positional and keyword bindings in their original AST order."""
    call = ast.parse("Row(((first := item), (second := item)), third=(third := item), last=(first, second, third))", mode="eval").body
    assert isinstance(call, ast.Call)
    arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
    expected = [node for argument in arguments for node in ast.walk(argument) if isinstance(node, ast.NamedExpr)]
    assert argument_dependencies(arguments) == expected


def test_same_argument_reads_are_not_dependencies() -> None:
    """Only reads in a later argument can make a binding dependent."""
    call = ast.parse("Row(((value := item), value), other=item)", mode="eval").body
    assert isinstance(call, ast.Call)
    assert argument_dependencies([*call.args, *(keyword.value for keyword in call.keywords)]) == []
