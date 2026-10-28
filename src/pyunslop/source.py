import io
import ast
import tokenize

NON_CODE_TOKENS = {tokenize.COMMENT, tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL}


class Source:
    """Collect lexical facts once for the independent comment rules."""

    def __init__(self, source: str, tree: ast.AST) -> None:
        """Combine AST line ranges with real comment and executable tokens."""
        self.lines = source.splitlines()
        self.function_starts: set[int] = set()
        self.standalone_comments: set[int] = set()
        self.continued_comments: set[int] = set()
        self.code_lines: set[int] = set()
        self.comments: list[tokenize.TokenInfo] = []
        import_lines, string_continuations = self.ast_lines(tree)
        self.collect_tokens(source, import_lines, string_continuations)

    def ast_lines(self, tree: ast.AST) -> tuple[set[int], set[int]]:
        """Identify imports and adjacent strings that physical counting overstates."""
        import_lines: set[int] = set()
        string_continuations: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.function_starts.add(node.lineno)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

            # Adjacent literals share one AST node across their physical source lines.
            elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
                string_continuations.update(range(node.lineno + 1, (node.end_lineno or node.lineno) + 1))
        return import_lines, string_continuations

    def collect_tokens(self, source: str, import_lines: set[int], string_continuations: set[int]) -> None:
        """Separate code, comment placement, and expression-continuation facts."""
        bracket_depth = 0
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            line_number, column = token.start
            if token.type == tokenize.COMMENT:
                # Hashes inside string literals never reach this token branch.
                self.comments.append(token)
                if not token.line[:column].strip():
                    self.standalone_comments.add(line_number)
                    if bracket_depth:
                        self.continued_comments.add(line_number)

            # Multiline and adjacent string tokens count only at their expression start.
            elif token.type not in NON_CODE_TOKENS:
                string_continuation = token.type == tokenize.STRING and line_number in string_continuations
                if line_number not in import_lines and not string_continuation:
                    self.code_lines.add(line_number)
                if token.type == tokenize.OP:
                    if token.string in ("(", "[", "{"):
                        bracket_depth += 1
                    elif token.string in (")", "]", "}"):
                        bracket_depth -= 1
