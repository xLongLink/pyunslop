from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .queries import QueryAnalyzer

SESSION_TYPES = {
    "sqlalchemy.orm.Session",
    "sqlalchemy.orm.session.Session",
    "sqlalchemy.engine.Connection",
    "sqlalchemy.engine.base.Connection",
    # Async sessions can produce buffered or streaming results depending on the method.
    "sqlalchemy.ext.asyncio.AsyncSession",
    "sqlalchemy.ext.asyncio.session.AsyncSession",
    "sqlalchemy.ext.asyncio.AsyncConnection",
    "sqlalchemy.ext.asyncio.engine.AsyncConnection",
    "sqlmodel.Session",
    "sqlmodel.orm.session.Session",
    "sqlmodel.ext.asyncio.session.AsyncSession",
}

# Factories return session constructors, not query results.
FACTORIES = {
    "sqlalchemy.orm.sessionmaker",
    "sqlalchemy.orm.session.sessionmaker",
    "sqlalchemy.ext.asyncio.async_sessionmaker",
    "sqlalchemy.ext.asyncio.session.async_sessionmaker",
}
QUERY_METHODS = {"execute", "scalars", "stream", "stream_scalars", "exec"}
RESULT_TRANSFORMS = {"scalars", "mappings", "unique", "tuples", "columns", "yield_per"}

# Result provenance must originate in a recognized annotation or library call.
RESULT_TYPES = {"Result", "ScalarResult", "MappingResult", "CursorResult", "AsyncResult", "AsyncScalarResult", "AsyncMappingResult"}
EXECUTE_RESULTS = {"@execute_result", "@single_execute_result"}
BUFFERED_RESULTS = {"@result", *EXECUTE_RESULTS}
RESULT_KINDS = {*BUFFERED_RESULTS, "@stream_result"}
SELECT_FUNCTIONS = {"sqlalchemy.select", "sqlalchemy.sql.select", "sqlmodel.select"}

# These constructors establish SQL ownership without guessing model attributes.
EXPRESSION_FUNCTIONS = {
    "sqlmodel.col",
    "sqlalchemy.column",
    "sqlalchemy.sql.column",
    "sqlalchemy.literal_column",
    "sqlalchemy.literal",
    "sqlalchemy.and_",
    "sqlalchemy.or_",
    "sqlalchemy.not_",
}

# These modifiers preserve the known selection shape.
STATEMENT_METHODS = {"where", "filter", "having", "group_by", "order_by", "limit", "offset", "join"}


def annotation_kind(name: str) -> str:
    """Classify session and result annotations without importing database packages."""
    if name in SESSION_TYPES:
        return "@session"
    module, _, symbol = name.rpartition(".")
    if (module == "sqlalchemy" or module.startswith("sqlalchemy.")) and symbol in RESULT_TYPES:
        return "@stream_result" if symbol.startswith("Async") else "@result"
    return ""


def kind(node: ast.Call, context: QueryAnalyzer) -> str:
    """Recognize constructors, factories, and expressions used by query rules."""
    name = context.qualified(node.func)
    if name in SESSION_TYPES or context.kind(node.func) == "@factory":
        return "@session"
    if name in FACTORIES:
        return "@factory"

    # Statement shape and expression ownership are shared by several query rules.
    if name in SELECT_FUNCTIONS:
        return "@single_statement" if len(node.args) == 1 and not isinstance(node.args[0], ast.Starred) else "@statement"
    if name in EXPRESSION_FUNCTIONS:
        return "@expression"
    if isinstance(node.func, ast.Attribute):
        return method_kind(node.func, node.args, context)
    return ""


def method_kind(method: ast.Attribute, arguments: list[ast.expr], context: QueryAnalyzer) -> str:
    """Propagate buffering through known query, result, and statement methods."""
    owner = context.kind(method.value)
    if owner == "@session" and method.attr in QUERY_METHODS:
        if method.attr == "execute":
            single = bool(arguments) and context.kind(arguments[0]) == "@single_statement"
            return "@single_execute_result" if single else "@execute_result"
        return "@stream_result" if method.attr.startswith("stream") else "@result"

    # Scalar transformations consume execute provenance without losing buffering.
    if owner in RESULT_KINDS and method.attr in RESULT_TRANSFORMS:
        if owner in EXECUTE_RESULTS and method.attr == "scalars":
            return "@result"
        return "@stream_result" if method.attr == "yield_per" else owner
    if owner in RESULT_KINDS and method.attr in {"all", "fetchall"}:
        return "@rows"
    if owner in {"@statement", "@single_statement"} and method.attr in STATEMENT_METHODS:
        return owner
    return ""
