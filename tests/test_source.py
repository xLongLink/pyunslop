import ast
from pathlib import Path
from pyunslop.source import Source


def test_source_encoding_is_respected(tmp_path: Path) -> None:
    """Honor a Python source encoding declaration when reading bytes."""
    path = tmp_path / "encoded.py"
    path.write_bytes(b'# coding: latin-1\nname = "caf\xe9"\n')
    facts = Source.read(path)
    assert facts.lines == ["# coding: latin-1", 'name = "café"']
    assert isinstance(facts.tree.body[0].value, ast.Constant)
    assert facts.tree.body[0].value.value == "café"


def test_standalone_comments_exclude_inline_comments_and_strings() -> None:
    """Only actual comment tokens may reset the standalone-comment counter."""

    # Arrange
    text = '# Heading\nvalue = "# not a comment"  # Inline\n\n# Next step\n'

    # Act
    facts = Source(text, ast.parse(text))

    # Assert
    assert [token.string for token in facts.comments] == ["# Heading", "# Inline", "# Next step"]
    assert facts.standalone_comments == {1, 4}
