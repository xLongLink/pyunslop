from pyunslop.source import Source
from pyunslop.analysis.queries import analyze_queries
from pyunslop.analysis.endpoints import analyze_endpoints
from pyunslop.diagnostics import Finding
from pyunslop.rules.pytest import check_pytest
from pyunslop.rules.pydantic import check_pydantic
from pyunslop.rules.module_doc import check_module_doc
from pyunslop.rules.simplifications import check_simplifications


def check_patterns(source: Source) -> list[Finding]:
    """Run independent syntax and domain checks over one parsed file."""
    findings = check_module_doc(source)
    findings.extend(check_pytest(source))
    findings.extend(check_pydantic(source))
    findings.extend(check_simplifications(source))
    findings.extend(analyze_queries(source.tree))
    findings.extend(analyze_endpoints(source.tree))
    return findings
