import tokenize
from pyunslop.source import Source
from pathlib import Path
from pyunslop.analysis import check_patterns
from pyunslop.diagnostics import Warning as CheckWarning
from pyunslop.rules.comments import check_comments


def check_file(path: Path) -> list[CheckWarning]:
    """Return fixed-preset warnings without editing files or raising findings.

    Unreadable or invalid source is skipped. All rules are enabled, with a fixed
    ten-point complexity budget. Function definitions and standalone comments reset SLOP001.
    """
    try:
        facts = Source.read(path)
    except (OSError, SyntaxError, UnicodeError, tokenize.TokenError):
        return []

    # Both rule families share one parse; sort their combined diagnostics by location.
    findings = [*check_comments(facts), *check_patterns(facts)]
    warnings = [CheckWarning(path, item.line, item.column, item.code, item.message) for item in findings]
    return sorted(warnings, key=lambda warning: (warning.line, warning.column, warning.code))
