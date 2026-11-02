import tokenize
from pathlib import Path
from itertools import chain
from pyunslop.source import Source
from pyunslop.analysis import check_patterns
from pyunslop.diagnostics import Diagnostic
from pyunslop.rules.comments import check_comments


def check_file(path: Path) -> list[Diagnostic]:
    """Return fixed-preset diagnostics without editing files or raising findings.

    Invalid source is skipped; file-read failures propagate. All rules are enabled, with a fixed
    ten-point complexity budget. Function definitions and standalone comments reset SLOP001.
    """
    try:
        facts = Source.read(path)
    except (SyntaxError, UnicodeError, tokenize.TokenError):
        return []

    # Both rule families share one parse; sort their combined diagnostics by location.
    findings = chain(check_comments(facts), check_patterns(facts))
    diagnostics = []
    for item in findings:
        column = item.column

        # AST columns count UTF-8 bytes; token-based findings already count characters.
        if item.byte_column:
            column = len(facts.lines[item.line - 1].encode("utf-8")[: column - 1].decode("utf-8")) + 1
        diagnostics.append(Diagnostic(path, item.line, column, item.code, item.message))
    return sorted(diagnostics, key=lambda diagnostic: (diagnostic.line, diagnostic.column, diagnostic.code))
