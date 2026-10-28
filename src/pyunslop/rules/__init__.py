from __future__ import annotations

from . import (
    cm001,
    cm002,
    cm003,
    py001,
    py002,
    py003,
    py004,
    py005,
    py006,
    py009,
    py010,
    py013,
    py014,
    py015,
    py101,
    py106,
    py107,
    py108,
    py109,
    py110,
    py111,
    py113,
    py114,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ast
    from typing import TypedDict
    from ..source import Source
    from ..analysis import AnalysisVisitor
    from ..contracts import LoopNode, FunctionNode, CommentFinding, ComprehensionNode
    from collections.abc import Callable

    RuleRegistry = TypedDict(
        "RuleRegistry",
        {
            "module": tuple[Callable[[ast.Module, AnalysisVisitor], None], ...],
            "module_exit": tuple[Callable[[ast.Module, AnalysisVisitor], None], ...],
            "function": tuple[Callable[[FunctionNode, AnalysisVisitor], None], ...],
            "function_exit": tuple[Callable[[FunctionNode, AnalysisVisitor], None], ...],
            "class": tuple[Callable[[ast.ClassDef, AnalysisVisitor], None], ...],
            # Binding hooks receive the exact statement form they inspect.
            "import": tuple[Callable[[ast.Import | ast.ImportFrom, AnalysisVisitor], None], ...],
            "assign": tuple[Callable[[ast.Assign, AnalysisVisitor], None], ...],
            "for": tuple[Callable[[LoopNode, AnalysisVisitor], None], ...],
            "attribute": tuple[Callable[[ast.Attribute, AnalysisVisitor], None], ...],
            # Expression hooks retain concrete node types rather than erasing them to AST.
            "return": tuple[Callable[[ast.Return, AnalysisVisitor], None], ...],
            "call": tuple[Callable[[ast.Call, AnalysisVisitor], None], ...],
            "comprehension": tuple[Callable[[ComprehensionNode, AnalysisVisitor], None], ...],
            "expression": tuple[Callable[[ast.Expr, AnalysisVisitor], None], ...],
        },
    )

COMMENT_RULES: tuple[Callable[[Source], list[CommentFinding]], ...] = (cm001.check, cm002.check, cm003.check)

# Event order preserves finding order and the scope in which each rule is evaluated.
AST_RULES: RuleRegistry = {
    "module": (py114.check,),
    "module_exit": (py014.check,),
    "function": (py114.check, py015.check, py110.check_function),
    "function_exit": (py009.check,),
    "class": (py110.check_class, py111.check),
    # Evaluate binding-sensitive rules before their enclosing visitor updates aliases.
    "import": (py013.check,),
    "assign": (py107.check_assign, py108.check_assign),
    "for": (py004.check, py108.check_for),
    "attribute": (py001.check,),
    "return": (py101.check, py010.check, py002.check),
    "call": (py003.check, py005.check, py006.check, py108.check_call, py109.check, py107.check_call),
    "comprehension": (py106.check,),
    "expression": (py113.check,),
}
