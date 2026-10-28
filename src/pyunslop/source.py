import io
import ast
import tokenize
from pathlib import Path


class Source:
    """Share parsed source and lexical facts across independent analyzers."""

    def __init__(self, source: str, tree: ast.Module) -> None:
        """Tokenize once and identify standalone comments shared by comment rules."""
        self.lines = source.splitlines()
        self.tree = tree
        self.tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        self.comments = [token for token in self.tokens if token.type == tokenize.COMMENT]
        self.standalone_comments = {token.start[0] for token in self.comments if not token.line[: token.start[1]].strip()}

    @classmethod
    def read(cls, path: Path) -> "Source":
        """Read Python's declared encoding and parse and tokenize exactly once."""
        with tokenize.open(path) as handle:
            text = handle.read()
        return cls(text, ast.parse(text))
