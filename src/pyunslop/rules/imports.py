import ast
from pyunslop.source import Source
from pyunslop.diagnostics import Finding


def check_imports(source: Source) -> list[Finding]:
    """Check absolute imports without resolving or executing dependencies."""
    findings = []
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Import):

            # One import statement can bind several unrelated dependencies.
            for alias in node.names:
                if alias.name == "src.errors" or alias.name.startswith("src.errors."):

                    # Point at the offending alias rather than the whole multi-import.
                    findings.append(
                        Finding.at(alias, "SLOP013", "do not import retired src.errors wrappers; use FastAPI HTTPException directly")
                    )

                # Submodule imports still establish a unittest dependency.
                if alias.name == "unittest" or alias.name.startswith("unittest."):
                    findings.append(Finding.at(alias, "SLOP016", "use pytest instead of unittest"))

        # Relative imports are deliberately unresolved rather than guessed.
        elif isinstance(node, ast.ImportFrom) and not node.level:

            # Include both submodule imports and `from src import errors`.
            if (
                node.module == "src.errors"
                or (node.module or "").startswith("src.errors.")
                or (node.module == "src" and any(alias.name == "errors" for alias in node.names))
            ):

                # From-imports share one module identity, so report the statement once.
                findings.append(Finding.at(node, "SLOP013", "do not import retired src.errors wrappers; use FastAPI HTTPException directly"))
            if node.module == "unittest" or (node.module or "").startswith("unittest."):
                findings.append(Finding.at(node, "SLOP016", "use pytest instead of unittest"))
    return findings
