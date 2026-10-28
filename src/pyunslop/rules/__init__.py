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
    py016,
    py017,
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
            "kind": tuple[Callable[[ast.AST, AnalysisVisitor], str], ...],
            "annotation": tuple[Callable[[str], str], ...],
        },
    )

COMMENT_RULES: tuple[Callable[[Source], list[CommentFinding]], ...] = (cm001.check, cm002.check, cm003.check)


def ast_rules() -> RuleRegistry:
    """Build the fixed registry with fresh rule-owned state for each file."""
    sequence = py002.Rule()
    schema = py009.Rule()
    module_doc = py014.Rule()
    parametrization = py015.Rule()
    validation = py101.Rule()
    walrus = py106.Rule()

    # Event order preserves finding order and the original alias scope.
    return {
        "module": (py114.check, parametrization.check_module),
        "module_exit": (module_doc.check,),
        "function": (py114.check, parametrization.check, py110.check_function, schema.check_function, validation.check_function),
        "function_exit": (schema.check,),
        "class": (validation.check_class, py017.check, py110.check_class, py111.check),
        # Binding-sensitive checks run before the visitor updates local aliases.
        "import": (py013.check, py016.check),
        "assign": (py107.check_assign, py108.check_assign),
        "for": (py004.check, py108.check_for),
        "attribute": (py001.check,),
        "return": (schema.check_return, validation.check, py010.check, sequence.check),
        "call": (module_doc.check_call, py003.check, py005.check, py006.check, py108.check_call, py109.check, py107.check_call),
        "comprehension": (walrus.check,),
        "expression": (py113.check,),
        # Classifiers contribute provenance without taking over scope traversal.
        "kind": (py010.kind, py009.kind),
        "annotation": (py009.annotation_kind,),
    }
