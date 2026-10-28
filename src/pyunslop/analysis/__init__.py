from ..source import Source
from .queries import analyze_queries
from .endpoints import analyze_endpoints
from ..diagnostics import Finding
from ..rules.pytest import check_pytest
from ..rules.imports import check_imports
from ..rules.pydantic import check_pydantic
from ..rules.module_doc import check_module_doc
from ..rules.simplifications import check_simplifications


def check_patterns(source: Source) -> list[Finding]:
    """Run independent syntax and domain checks over one parsed file."""
    findings = check_imports(source)
    findings.extend(check_module_doc(source))
    findings.extend(check_pytest(source))
    findings.extend(check_pydantic(source))
    findings.extend(check_simplifications(source))
    findings.extend(analyze_queries(source.tree))
    findings.extend(analyze_endpoints(source.tree))
    return findings
