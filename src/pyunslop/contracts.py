import ast
from collections.abc import Callable

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
LoopNode = ast.For | ast.AsyncFor
WithNode = ast.With | ast.AsyncWith
ScopeNode = ast.Module | FunctionNode
ComprehensionNode = ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
LocatedNode = ast.stmt | ast.expr | ast.alias | ast.arg
QualifiedName = Callable[[ast.AST | None], str]
