import tokenize
from .source import Source
from pathlib import Path
from .analysis import check_patterns
from .diagnostics import Warning as CheckWarning
from .rules.comments import check_comments


def check_file(path: Path) -> list[CheckWarning]:
    """Return fixed-preset warnings without editing files or raising findings.

    Unreadable or invalid source is skipped. All rules are enabled, with a fixed
    ten-line comment limit. Function definitions and standalone comments reset CM001.
    """
    try:
        facts = Source.read(path)
    except (OSError, SyntaxError, UnicodeError, tokenize.TokenError):
        return []
    findings = [*check_comments(facts), *check_patterns(facts)]
    warnings = [CheckWarning(path, item.line, item.column, item.code, item.message) for item in findings]
    return sorted(warnings, key=lambda warning: (warning.line, warning.column, warning.code))
