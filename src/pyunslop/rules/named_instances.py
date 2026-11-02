from __future__ import annotations

import ast
import tokenize
from typing import TYPE_CHECKING
from pathlib import Path
from pyunslop.diagnostics import Finding

if TYPE_CHECKING:
    from pyunslop.analysis.bindings import BindingVisitor

CODE = "SLOP009"


def named_assignment(node: ast.Call, parent: ast.AST | None) -> bool:
    """Recognize direct construction assigned only to ordinary names."""
    if not isinstance(parent, (ast.Assign, ast.AnnAssign)) or parent.value is not node:
        return False
    targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
    return all(isinstance(target, ast.Name) for target in targets)


def method_receiver(node: ast.Call, parents: list[ast.AST]) -> bool:
    """Follow attributes from construction to an immediately invoked method."""
    owner: ast.AST = node

    # Calling the constructed object itself is not a method call.
    for ancestor in reversed(parents[:-1]):
        if isinstance(ancestor, ast.Attribute) and ancestor.value is owner:
            owner = ancestor
            continue
        return owner is not node and isinstance(ancestor, ast.Call) and ancestor.func is owner
    return False


# Local source is the only evidence used for imported constructors.
class Constructors:
    """Resolve declared classes without importing or executing inspected modules."""

    def __init__(self, path: Path | None) -> None:
        """Limit import lookup to adjacent modules and the containing package root."""
        self.path = path.resolve() if path else None
        self.roots: list[Path] = []
        self.definitions: dict[str, ast.ClassDef] = {}
        self.modules: dict[str, ast.Module | None] = {}

        # Absolute imports start outside the containing package.
        if self.path:
            root = self.path.parent
            while (root / "__init__.py").is_file():
                root = root.parent
            self.roots = list(dict.fromkeys((self.path.parent, root)))

    def register(self, node: ast.ClassDef) -> str:
        """Keep distinct declarations separate even when their names coincide."""
        key = f"@class:{id(node)}"
        self.definitions[key] = node
        return key

    def module(self, name: str, level: int = 0) -> str:
        """Find local Python modules without consulting installed packages."""
        roots = self.roots
        if level:
            if self.path is None:
                return ""
            root = self.path.parent

            # Relative imports stay anchored to the inspected file.
            for _ in range(level - 1):
                root = root.parent
            roots = [root]

        # Inspect source files only; never run an import loader.
        candidates = []
        for root in roots:
            target = root.joinpath(*name.split(".")) if name else root
            candidates.extend((target.with_suffix(".py"), target / "__init__.py"))
        return next((f"@module:{candidate}" for candidate in candidates if candidate.is_file()), "")

    def load(self, filename: str) -> ast.Module | None:
        """Cache parsed local modules, including unreadable or invalid source."""
        if filename in self.modules:
            return self.modules[filename]

        try:

            # Honor source encodings without executing module code.
            with tokenize.open(filename) as handle:
                self.modules[filename] = ast.parse(handle.read())
        except (OSError, SyntaxError, UnicodeError):
            self.modules[filename] = None
        return self.modules[filename]

    def member(self, owner: str, name: str) -> str:
        """Recognize direct class declarations in a class or local module."""
        definition: ast.ClassDef | ast.Module | None = self.definitions.get(owner)
        if owner.startswith("@module:"):
            definition = self.load(owner.removeprefix("@module:"))
        if definition is None:
            return ""
        body = definition.body

        # Rebound exports do not prove that callers receive a class.
        matches = [node for node in body if isinstance(node, ast.ClassDef) and node.name == name]
        if len(matches) != 1 or matches[0].decorator_list:
            return ""

        # Conservatively reject writes even inside conditional or nested scopes.
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == name:
                return ""
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return ""

            # An imported replacement can be a function rather than a class.
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if any((alias.asname or alias.name.split(".")[0]) == name for alias in node.names):
                    return ""
        return self.register(matches[0])

    def resolve(self, node: ast.expr, context: BindingVisitor) -> str:
        """Follow proven class and module aliases, not naming conventions."""
        if isinstance(node, ast.Name):
            return context.kind(node)
        if isinstance(node, ast.Attribute):
            return self.member(self.resolve(node.value, context), node.attr)
        return ""

    def check(self, node: ast.Call, context: BindingVisitor) -> list[Finding]:
        """Require separate names and multiline argument-bearing construction."""
        definition = self.definitions.get(self.resolve(node.func, context))
        if definition is None:
            return []
        parent = context.parents[-2] if len(context.parents) > 1 else None

        # Empty constructors need a name, but not artificial line breaks.
        if named_assignment(node, parent):
            if (node.args or node.keywords) and node.lineno == node.end_lineno:
                return [Finding.at(node, CODE, f"split the {definition.name} constructor assignment across multiple lines")]
            return []

        # Follow attribute access, stopping before unrelated enclosing calls.
        if method_receiver(node, context.parents):
            return [Finding.at(node, CODE, f"assign the {definition.name} instance to a name before calling its methods")]
        return []
