import ast

ITERABLE_CONSUMERS = {"sum", "min", "max", "tuple", "set", "frozenset"}
CLI_HELP_APIS = {"argparse.ArgumentParser", "click.command", "click.group", "typer.Typer"}


def uses_cli_doc(call, qualified):
    return qualified(call.func) in CLI_HELP_APIS and any(
        keyword.arg in {"description", "epilog", "help"}
        and any(isinstance(node, ast.Name) and node.id == "__doc__" for node in ast.walk(keyword.value))
        for keyword in call.keywords
    )


def single_literal_case(decorator, qualified):
    if not isinstance(decorator, ast.Call) or qualified(decorator.func) != "pytest.mark.parametrize":
        return False
    options = {keyword.arg: keyword.value for keyword in decorator.keywords}
    if any(key in options for key in (None, "ids", "scope")):
        return False
    indirect = options.get("indirect")
    if indirect is not None and not (isinstance(indirect, ast.Constant) and indirect.value is False):
        return False

    # pytest.param, marks, and dynamically computed cases may affect collection.
    values = decorator.args[1] if len(decorator.args) > 1 else options.get("argvalues")
    if not isinstance(values, (ast.List, ast.Tuple)) or len(values.elts) != 1:
        return False
    try:
        ast.literal_eval(values.elts[0])
    except (ValueError, TypeError):
        return False
    return True


def forwarded_function(node):
    if not node.name.startswith("_") or node.name.endswith("__") or node.decorator_list or node.returns:
        return False
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.defaults or node.args.kw_defaults or any(arg.annotation for arg in args):
        return False
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
        return False

    # Awaiting the forwarded call is compatible with an otherwise transparent wrapper.
    call = node.body[0].value
    if isinstance(call, ast.Await):
        call = call.value

    # Only exact positional forwarding is transparent enough to suggest review.
    if not isinstance(call, ast.Call) or call.keywords or node.args.vararg or node.args.kwarg:
        return False
    if isinstance(call.func, ast.Name) and call.func.id == node.name:
        return False
    return len(call.args) == len(args) and all(
        isinstance(value, ast.Name) and value.id == arg.arg
        for value, arg in zip(call.args, args)
    )


def empty_subclass(node, qualified):
    if node.decorator_list or node.keywords or len(node.bases) != 1 or ast.get_docstring(node):
        return False
    if not (node.name.startswith("_") or qualified(node.bases[0]) in {
        "fastapi.testclient.TestClient", "starlette.testclient.TestClient",
    }):
        return False

    # A docstring or any actual statement would establish an intentional boundary.
    return all(
        isinstance(statement, ast.Pass)
        or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and statement.value.value is Ellipsis)
        for statement in node.body
    )


def borrowed_client_class(node):
    if node.bases or node.keywords or node.decorator_list or ast.get_docstring(node):
        return False
    methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(methods) != len(node.body) or len(methods) < 2:
        return False
    constructor = next((method for method in methods if method.name == "__init__"), None)
    if constructor is None or len(constructor.body) != 1 or len(constructor.args.args) != 2:
        return False

    # Multiple initialization statements imply state or setup beyond a borrowed client.
    assignment = constructor.body[0]
    if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
        return False

    # Ownership must be borrowed directly, not created by a constructor or factory.
    target = assignment.targets[0]
    client = constructor.args.args[1].arg
    if not (client == "client" or client.endswith("_client")):
        return False
    if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"):
        return False
    if not isinstance(assignment.value, ast.Name) or assignment.value.id != client:
        return False

    # Properties, lifecycle hooks, and uses of self beyond the borrowed field add behavior.
    for method in methods:
        if method.decorator_list or ast.get_docstring(method):
            return False
        if method is not constructor and method.name.startswith("__"):
            return False

        # Rebinding state or exposing self to another object makes removal nontrivial.
        for parent in ast.walk(method):
            if method is not constructor and isinstance(parent, ast.Attribute) and isinstance(parent.ctx, (ast.Store, ast.Del)):
                return False
            for child in ast.iter_child_nodes(parent):
                if isinstance(child, ast.Name) and child.id == "self":
                    if not isinstance(parent, ast.Attribute) or parent.attr != target.attr:
                        return False
    return True


def comprehension_dependencies(node):
    roots = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
    findings = []
    for root in roots:
        for call in (item for item in ast.walk(root) if isinstance(item, ast.Call)):
            name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
            if not name.lstrip("_")[:1].isupper():
                continue

            # Constructor arguments are evaluated left to right, including keywords.
            arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
            findings.extend(argument_dependencies(arguments))
    return findings


def argument_dependencies(arguments):
    findings = []
    for index, argument in enumerate(arguments):
        bindings = [node for node in ast.walk(argument) if isinstance(node, ast.NamedExpr)]
        later = [node for value in arguments[index + 1:] for node in ast.walk(value)]
        for binding in bindings:
            if any(isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == binding.target.id for node in later):
                findings.append(binding)
    return findings


def simple_comprehension(node):
    if not isinstance(node, ast.ListComp):
        return False
    if any(isinstance(child, (ast.Call, ast.Await, ast.Yield, ast.NamedExpr, ast.Lambda)) for child in ast.walk(node)):
        return False
    return all(not generator.is_async and not generator.ifs for generator in node.generators)


def iterable_materialization(call, qualified):
    return (
        qualified(call.func) in ITERABLE_CONSUMERS and len(call.args) == 1
        and not call.keywords and simple_comprehension(call.args[0])
    )


def name_loads(function, name):
    return [
        (node, parent) for parent in ast.walk(function) for node in ast.iter_child_nodes(parent)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name
    ]


def scope_nodes(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from scope_nodes(child)


def size_use(node, parent, qualified):
    if isinstance(parent, ast.Call):
        return qualified(parent.func) in {"len", "bool"} and parent.args == [node] and not parent.keywords
    if isinstance(parent, (ast.If, ast.While, ast.IfExp)):
        return parent.test is node
    return isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not)


def only_size_uses(function, name, qualified):
    uses = name_loads(function, name)
    stores = [node for node in scope_nodes(function) if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store)]
    return len(stores) == 1 and bool(uses) and all(size_use(node, parent, qualified) for node, parent in uses)


def temporary_iterable_pair(function, assignment, following, qualified):
    if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1:
        return []
    target = assignment.targets[0]
    if not isinstance(target, ast.Name) or not simple_comprehension(assignment.value):
        return []
    uses = name_loads(function, target.id)
    if len(uses) != 1:
        return []
    node, consumer = uses[0]

    # Require an immediately adjacent consumption; intervening code may need a snapshot.
    if not isinstance(consumer, ast.Call) or getattr(following, "value", None) is not consumer:
        return []
    if qualified(consumer.func) in ITERABLE_CONSUMERS and consumer.args == [node] and not consumer.keywords:
        return [(assignment.value, "PY107", "review a generator for this single-use list; preserve snapshot and exception timing")]
    return []


def method_call(statement):
    if not isinstance(statement, ast.Expr):
        return None
    value = statement.value
    if isinstance(value, ast.Await):
        value = value.value
    return value if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) else None


def immutable_literal(node):
    """Recognize literals without mutable members or runtime computation."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Tuple):
        return all(immutable_literal(element) for element in node.elts)
    if not isinstance(node, ast.UnaryOp) or not isinstance(node.op, (ast.UAdd, ast.USub)):
        return False
    return isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float, complex)


def mentions_binding(node, name):
    """Include bindings stored as strings rather than Name nodes."""
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.arg):
        return node.arg == name
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name

    # Imports, declarations, and captures may bind names without a Name node.
    if isinstance(node, ast.alias):
        return (node.asname or node.name.split(".")[0]) == name
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return name in node.names

    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
        return node.name == name
    return isinstance(node, ast.MatchMapping) and node.rest == name


def single_use_constants(scope):
    """Find conservative, same-scope literal-inlining review candidates."""
    nodes = list(ast.walk(scope))
    if any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {"globals", "locals", "vars", "eval", "exec"}
        for node in nodes
    ):
        return []

    # Export lists can publish private names through string references.
    if isinstance(scope, ast.Module) and any(isinstance(node, ast.Name) and node.id == "__all__" for node in nodes):
        return []

    # Nested scopes and comprehensions can capture or shadow an otherwise single use.
    boundaries = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    nested = [child for node in nodes if node is not scope and isinstance(node, boundaries) for child in ast.walk(node)]
    findings = []
    for statement in scope.body:
        target = constant_target(statement, isinstance(scope, ast.Module))
        if target is None:
            continue

        # Only a single store and a later read establish a local review candidate.
        references = [node for node in nodes if mentions_binding(node, target.id)]
        if len(references) != 2 or any(mentions_binding(node, target.id) for node in nested):
            continue
        uses = [node for node in references if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)]
        if len(uses) == 1 and (uses[0].lineno, uses[0].col_offset) > (statement.end_lineno, statement.end_col_offset):
            findings.append((
                target, "PY114",
                f"review inlining single-use constant {target.id}; preserve meaningful names and intentional boundaries",
            ))
    return findings


def constant_target(statement, private_only):
    """Keep annotated contracts, public module APIs, and computed values intact."""
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or statement.type_comment:
        return None
    target = statement.targets[0]
    if not isinstance(target, ast.Name) or not target.id.isupper() or not immutable_literal(statement.value):
        return None
    return target if not private_only or target.id.startswith("_") else None
