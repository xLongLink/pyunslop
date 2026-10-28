from __future__ import annotations

import ast
from ..diagnostics import Finding

CODE = "PY111"


def borrowed_client_class(node: ast.ClassDef) -> bool:
    """Recognize plain classes whose sole state is a directly borrowed client."""
    if node.bases or node.keywords or node.decorator_list or ast.get_docstring(node):
        return False
    methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(methods) != len(node.body) or len(methods) < 2:
        return False

    # Require a constructor that accepts exactly self and the borrowed dependency.
    constructor = next((method for method in methods if method.name == "__init__"), None)
    if constructor is None or len(constructor.body) != 1 or len(constructor.args.args) != 2:
        return False

    # Initialization must not establish extra state or acquire an owned client.
    assignment = constructor.body[0]
    if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
        return False
    target = assignment.targets[0]
    client = constructor.args.args[1].arg
    if not (client == "client" or client.endswith("_client")):
        return False

    # The client must be stored directly on this instance.
    if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"):
        return False

    # A constructed or transformed client has ownership semantics worth retaining.
    if not isinstance(assignment.value, ast.Name) or assignment.value.id != client:
        return False

    # Properties, hooks, rebinding, and exposing self establish meaningful behavior.
    for method in methods:
        if method.decorator_list or ast.get_docstring(method):
            return False
        if method is not constructor and method.name.startswith("__"):
            return False

        # State changes outside construction make the wrapper meaningful.
        for parent in ast.walk(method):
            if method is not constructor and isinstance(parent, ast.Attribute) and isinstance(parent.ctx, (ast.Store, ast.Del)):
                return False

            # Every use of self must resolve only to the originally borrowed field.
            for child in ast.iter_child_nodes(parent):
                if isinstance(child, ast.Name) and child.id == "self":
                    # Passing self elsewhere can expose behavior beyond the borrowed client.
                    if not isinstance(parent, ast.Attribute) or parent.attr != target.attr:
                        return False
    return True


def check(node: ast.ClassDef) -> list[Finding]:
    """Suggest reviewing namespaced functions without removing client boundaries."""
    if borrowed_client_class(node):
        return [Finding.at(node, CODE, "review this borrowed-client-only class as namespaced functions; preserve meaningful boundaries")]
    return []
