import ast
import codecs
import pytest
from pathlib import Path
from pyunslop.source import Source
from pyunslop.checker import check_file


@pytest.mark.parametrize(("encoding", "prefix"), [("utf-8", b""), ("utf-8", codecs.BOM_UTF8), ("latin-1", b"")])
def test_declared_encodings_share_text_ast_and_comments(tmp_path: Path, encoding: str, prefix: bytes) -> None:
    """Decode declared encodings before deriving both syntax and lexical facts."""
    text = f"# coding: {encoding}\nvalue = 'café'\n# Explain the value.\n"
    path = tmp_path / "example.py"
    path.write_bytes(prefix + text.encode(encoding))

    # Act
    source = Source.read(path)

    # Assert
    assert source.lines == text.splitlines()
    assignment = source.tree.body[0]
    assert isinstance(assignment, ast.Assign)
    assert isinstance(assignment.value, ast.Constant)
    assert assignment.value.value == "café"
    assert [comment.string for comment in source.comments] == [f"# coding: {encoding}", "# Explain the value."]
    assert source.standalone_comments == {1, 3}


def test_syntax_errors_precede_tokenization_errors() -> None:
    """Keep parsing first when an unterminated string would also fail tokenization."""
    with pytest.raises(SyntaxError):
        Source("value = '''")


def test_conflicting_bom_and_encoding_cookie_remain_invalid_source(tmp_path: Path) -> None:
    """Preserve declared-encoding failures and the native checker's invalid-source skip."""
    path = tmp_path / "example.py"
    path.write_bytes(codecs.BOM_UTF8 + b"# coding: latin-1\nvalue = 1\n")

    # Act / Assert
    with pytest.raises(SyntaxError):
        Source.read(path)
    assert check_file(path) == []
