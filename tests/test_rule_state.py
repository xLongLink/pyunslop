import ast
import pytest
import textwrap
from test_support import check_patterns


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            """
            from sqlalchemy.engine import Result
            def fetch(result: Result) -> list[User]:
                if condition:
                    return result.all()
                return result.all()
            """,
            ["PY002"],
        ),
        # The outer and inner comprehensions both reach the same walrus binding.
        ("rows = [[Row(x=(value := item), y=value) for item in group] for group in groups]", ["PY106"]),
    ],
)
def test_deduplication_is_local_to_one_analysis(source: str, expected: list[str]) -> None:
    """Rechecking the identical tree must neither lose nor duplicate findings."""
    tree = ast.parse(textwrap.dedent(source))
    for _ in range(2):
        assert [finding.code for finding in check_patterns(tree)] == expected


@pytest.mark.parametrize(
    ("exempt", "flagged", "expected"),
    [
        ('"""Help."""\nimport argparse\nparser = argparse.ArgumentParser(description=__doc__)', '"""Not CLI help."""', ["PY014"]),
        # Collection hooks suppress parametrization warnings only within their module.
        (
            "import pytest\ndef pytest_generate_tests(metafunc): pass\n@pytest.mark.parametrize('value', [1])\ndef test_value(value): pass",
            "import pytest\n@pytest.mark.parametrize('value', [1])\ndef test_value(value): pass",
            ["PY015"],
        ),
    ],
)
def test_module_exemptions_do_not_leak(exempt: str, flagged: str, expected: list[str]) -> None:
    """Each new analysis must start without earlier modules' exemptions."""
    assert check_patterns(ast.parse(exempt)) == []
    tree = ast.parse(flagged)
    assert [finding.code for finding in check_patterns(tree)] == expected
    assert check_patterns(ast.parse(exempt)) == []


def test_response_model_exemptions_do_not_leak() -> None:
    """A transforming model in one file must not exempt another file's model."""
    route = "\nfrom fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/', response_model=Model)\ndef fetch():\n    return Model.model_validate(value)"
    transforming = "class Model:\n    def model_post_init(self): pass\n"
    assert check_patterns(ast.parse(transforming + route)) == []
    assert [finding.code for finding in check_patterns(ast.parse(route))] == ["PY101"]


def test_raw_returns_belong_to_their_function() -> None:
    """An enclosing raw-response endpoint must not exempt a nested JSON endpoint."""
    source = """
    from fastapi import APIRouter, Response
    router = APIRouter()
    @router.get('/outer')
    def outer():
        @router.get('/inner')
        def inner():
            return {'value': 1}
        return Response()
    """
    findings = check_patterns(ast.parse(textwrap.dedent(source)))
    assert [(finding.line, finding.code) for finding in findings] == [(6, "PY009")]
