import ast
import textwrap
import unittest
from pyunslop.analysis import check_patterns


def codes(source: str) -> list[str]:
    """Return native warning codes from a dedented review-rule fixture."""
    return [code for _, code, _ in check_patterns(ast.parse(textwrap.dedent(source)))]


class RepositoryPolicyTests(unittest.TestCase):
    """Check the fixed import and module-documentation policies."""

    def test_policies_are_always_enabled(self) -> None:
        """Enable both repository policies without requiring configuration."""
        source = '"""Module docs."""\nfrom src.errors import ConflictError\n'
        assert sorted(codes(source)) == ["PY013", "PY014"]

    def test_retired_import_forms(self) -> None:
        """Reject absolute imports of retired wrappers and their submodules."""
        for source in (
            "from src.errors import ConflictError",
            "import src.errors as errors",
            "from src import errors",
            "import src.errors.http",
            "from src.errors.http import ConflictError",
        ):
            # Act / Assert: each retired absolute import form must be rejected.
            with self.subTest(source=source):
                assert codes(source) == ["PY013"]

    def test_unrelated_imports_and_http_exception_are_allowed(self) -> None:
        """Allow unrelated error modules and direct FastAPI HTTP exceptions."""
        assert codes("from other.errors import ConflictError\nfrom fastapi import HTTPException") == []

    def test_module_docstring_only(self) -> None:
        """Keep function docstrings outside the leading-module-docstring policy."""
        assert codes('def fn():\n    """Function docs."""\n    pass\n') == []

    def test_cli_help_exemption(self) -> None:
        """Allow module documentation used explicitly as argparse help."""
        source = '''\
        """Command help."""
        from argparse import ArgumentParser as Parser
        parser = Parser(description=__doc__)
        '''
        assert codes(source) == []

    def test_merely_referencing_doc_is_not_cli_help(self) -> None:
        """Require a recognized CLI-help use rather than any reference to __doc__."""
        source = '"""Module docs."""\nprint(__doc__)\n'
        assert codes(source) == ["PY014"]


class ParametrizationTests(unittest.TestCase):
    """Distinguish redundant literal cases from meaningful collection behavior."""

    def test_single_literal_case(self) -> None:
        """Flag one literal case in list and tuple parametrization forms."""
        for values in ('["acme"]', '[("acme", 1)]', '("acme",)'):
            with self.subTest(values=values):
                source = f'import pytest\n@pytest.mark.parametrize("name", {values})\ndef test_name(name):\n    assert name\n'
                assert codes(source) == ["PY015"]

    def test_keyword_case_and_mark_alias(self) -> None:
        """Recognize imported mark aliases and keyword-style parametrization."""
        source = """
        from pytest import mark as testmark
        @testmark.parametrize(argnames="name", argvalues=["acme"])
        def test_name(name):
            assert name
        """
        assert codes(source) == ["PY015"]

    def test_fixture_collection_and_dynamic_cases_are_preserved(self) -> None:
        """Preserve indirect fixtures, IDs, marks, scopes, and dynamic or multiple cases."""
        for arguments in (
            '"name", ["acme"], indirect=True',
            '"name", ["acme"], ids=["contract-id"]',
            '"name", ["acme"], scope="module"',
            '"name", [pytest.param("acme", marks=pytest.mark.slow)]',
            '"name", cases',
            '"name", ["acme", "other"]',
        ):
            # Act / Assert: preserve fixture, collection, and dynamic-case exemptions.
            with self.subTest(arguments=arguments):
                source = f"import pytest\n@pytest.mark.parametrize({arguments})\ndef test_name(name):\n    assert name\n"
                assert codes(source) == []

    def test_request_fixture_is_preserved(self) -> None:
        """Retain parametrization when request may inspect collection metadata."""
        source = """
        import pytest
        @pytest.mark.parametrize("name", ["acme"])
        def test_name(name, request):
            assert request.node.callspec
        """
        assert codes(source) == []

    def test_collection_hook_is_preserved(self) -> None:
        """Preserve cases in modules whose collection hooks can depend on them."""
        source = """
        import pytest
        def pytest_collection_modifyitems(items):
            pass
        @pytest.mark.parametrize("name", ["acme"])
        def test_name(name):
            assert name
        """
        assert codes(source) == []


class ResponseValidationTests(unittest.TestCase):
    """Review duplicate route validation while retaining intentional transformations."""

    def test_repeated_response_validation(self) -> None:
        """Recognize reconstruction using the same model declared by the route."""
        source = """
        from fastapi import APIRouter
        from models import UserResponse as Output
        router = APIRouter()
        @router.get('/me', response_model=Output)
        async def me(user):
            return Output.model_validate(user)
        """
        assert codes(source) == ["PY101"]

    def test_explicit_transformations_are_preserved(self) -> None:
        """Retain explicit validation options, computed inputs, and different models."""
        for expression in (
            "Output.model_validate(user, from_attributes=True)",
            "Output.model_validate(transform(user))",
            "Other.model_validate(user)",
        ):
            with self.subTest(expression=expression):
                source = f"from fastapi import FastAPI\napp = FastAPI()\n@app.get('/', response_model=Output)\ndef endpoint(user):\n    return {expression}\n"
                assert codes(source) == []

    def test_local_model_validators_are_preserved(self) -> None:
        """Keep reconstruction when a visible validator can transform the model."""
        source = """
        from fastapi import FastAPI
        from pydantic import BaseModel, model_validator
        class Output(BaseModel):
            @model_validator(mode='after')
            def normalize(self):
                return self
        app = FastAPI()
        @app.get('/', response_model=Output)
        def endpoint(user):
            return Output.model_validate(user)
        """
        assert codes(source) == []

    def test_different_route_contracts_are_preserved(self) -> None:
        """Avoid removing reconstruction shared by routes with different schemas."""
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/one', response_model=Output)
        @app.get('/two', response_model=OtherOutput)
        def endpoint(user):
            return Output.model_validate(user)
        """
        assert codes(source) == []


class ComprehensionReviewTests(unittest.TestCase):
    """Check constructor-argument dependencies inside comprehension expressions."""

    def test_constructor_argument_dependency(self) -> None:
        """Detect a walrus value reused by a later constructor argument."""
        source = """
        rows = [Audit(deleted_at=(deleted_at := latest(member)),
                      updated_at=max(member.updated_at, deleted_at or member.updated_at))
                for member in members]
        """
        assert codes(source) == ["PY106"]

    def test_independent_binding_and_non_comprehension_are_allowed(self) -> None:
        """Allow independent walrus bindings and ordinary non-comprehension calls."""
        source = """
        rows = [Audit(deleted_at=(deleted_at := latest(member))) for member in members]
        row = Audit(deleted_at=(deleted_at := latest(member)), updated_at=deleted_at)
        """
        assert codes(source) == []

    def test_generator_constructor_dependency(self) -> None:
        """Apply constructor-dependency checks to generator expressions too."""
        assert codes("rows = (Audit(first=(value := source(item)), second=value) for item in items)") == ["PY106"]


class MaterializationReviewTests(unittest.TestCase):
    """Limit iterable materialization reviews to conservative single-use candidates."""

    def test_direct_iterable_consumer(self) -> None:
        """Review a list comprehension consumed directly by a known iterable API."""
        assert codes("total = sum([invoice.amount for invoice in invoices])") == ["PY107"]

    def test_adjacent_single_use_temporary(self) -> None:
        """Review a temporary list consumed only by the next statement."""
        source = """
        def total(invoices):
            amounts = [invoice.amount for invoice in invoices]
            return sum(amounts)
        """
        assert codes(source) == ["PY107"]

    def test_reused_or_snapshot_lists_are_preserved(self) -> None:
        """Retain reused lists and snapshots separated from their consumer by work."""
        for body in (
            "amounts = [invoice.amount for invoice in invoices]\n    log(amounts)\n    return sum(amounts)",
            "amounts = [invoice.amount for invoice in invoices]\n    mutate(invoices)\n    return sum(amounts)",
            "amounts = [invoice.amount for invoice in invoices]\n    return mutate(invoices) + sum(amounts)",
        ):
            with self.subTest(body=body):
                assert codes("def total(invoices):\n    " + body) == []

    def test_side_effecting_and_short_circuiting_expressions_are_preserved(self) -> None:
        """Keep eager evaluation when calls or short-circuiting affect timing."""
        for expression in ("sum([load(x) for x in xs])", "any([item.flag for item in items])", "all([item.flag for item in items])"):
            with self.subTest(expression=expression):
                assert codes(expression) == []

    def test_unknown_consumers_are_ignored(self) -> None:
        """Do not assume an unknown consumer accepts lazy iterables."""
        assert codes("consume([invoice.amount for invoice in invoices])") == []

    def test_shadowed_consumers_are_preserved(self) -> None:
        """Require builtin consumer identity after parameters or assignments shadow names."""
        for prefix in ("def total(invoices, sum):\n", "def total(invoices):\n    sum = custom\n"):
            with self.subTest(prefix=prefix):
                source = prefix + "    amounts = [invoice.amount for invoice in invoices]\n    return sum(amounts)\n"
                assert codes(source) == []

    def test_closure_snapshot_is_preserved(self) -> None:
        """Count a nested closure's reference as reuse of the materialized snapshot."""
        source = """
        def total(invoices):
            amounts = [invoice.amount for invoice in invoices]
            def later():
                return amounts
            value = sum(amounts)
            return value, later
        """
        assert codes(source) == []


class QueryReviewTests(unittest.TestCase):
    """Review query API choices without rewriting cardinality or transaction behavior."""

    def test_scalar_api_preserves_cardinality(self) -> None:
        """Recommend scalars without dropping the one_or_none cardinality check."""
        source = """
        from sqlalchemy.ext.asyncio import AsyncSession
        async def fetch(s: AsyncSession):
            result = await s.execute(stmt)
            return result.scalars().one_or_none()
        """
        assert codes(source) == ["PY108"]

    def test_single_column_unpacking(self) -> None:
        """Review loop unpacking from a known single-selection query."""
        source = """
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        async def fetch(s: AsyncSession):
            result = await s.execute(select(User))
            for user, in result:
                consume(user)
        """
        assert codes(source) == ["PY108"]

    def test_single_row_unpacking(self) -> None:
        """Review one-element row unpacking while retaining its cardinality check."""
        source = """
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        async def fetch(s: AsyncSession):
            result = await s.execute(select(User))
            user, = result.one()
        """
        assert codes(source) == ["PY108"]

    def test_multi_column_unpacking_is_preserved(self) -> None:
        """Retain row consumption when multiple selected columns are required."""
        source = """
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        async def fetch(s: AsyncSession):
            result = await s.execute(select(User.id, User.name))
            for user_id, name in result:
                consume(user_id, name)
        """
        assert codes(source) == []

    def test_direct_existence_or_threshold_materialization(self) -> None:
        """Review rows loaded directly for truth or threshold comparisons."""
        for expression in ("bool(result.all())", "len(result.all()) > 3"):
            with self.subTest(expression=expression):
                source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def exists(s: AsyncSession):\n    result = await s.scalars(stmt)\n    return {expression}\n"
                assert codes(source) == ["PY109"]

    def test_named_size_only_materialization(self) -> None:
        """Follow a named row list used only for a length comparison."""
        source = """
        from sqlalchemy.ext.asyncio import AsyncSession
        async def exists(s: AsyncSession):
            result = await s.scalars(stmt)
            rows = result.all()
            return len(rows) >= threshold
        """
        assert codes(source) == ["PY109"]

    def test_rows_used_as_data_are_preserved(self) -> None:
        """Keep materialized rows when another consumer needs their data."""
        source = """
        from sqlalchemy.ext.asyncio import AsyncSession
        async def fetch(s: AsyncSession):
            result = await s.scalars(stmt)
            rows = result.all()
            consume(rows)
            return len(rows)
        """
        assert codes(source) == []

    def test_immediate_refresh_candidate(self) -> None:
        """Review a refresh immediately following a same-session commit."""
        source = """
        from sqlalchemy.ext.asyncio import AsyncSession
        async def save(s: AsyncSession, item):
            s.add(item)
            await s.commit()
            await s.refresh(item)
            return item
        """
        assert codes(source) == ["PY113"]

    def test_different_sessions_and_intervening_work_are_preserved(self) -> None:
        """Keep refreshes on other sessions or separated from commit by work."""
        source = """
        from sqlalchemy.ext.asyncio import AsyncSession
        async def save(s: AsyncSession, other: AsyncSession, item):
            await s.commit()
            await other.refresh(item)
            await s.commit()
            consume(item)
            await s.refresh(item)
        """
        assert codes(source) == []


class SingleUseConstantTests(unittest.TestCase):
    """Check literal candidates and scope/export safeguards."""

    def test_local_literals(self) -> None:
        """Include signed numbers and recursively immutable tuples."""
        for literal in ("30", "-30", "+2.5", '"ready"', 'b"ready"', "True", "None", '(1, "ready", (-2, None))'):
            with self.subTest(literal=literal):
                assert codes(f"def run():\n    VALUE = {literal}\n    return consume(VALUE)\n") == ["PY114"]

    def test_private_module_constant_and_location(self) -> None:
        """Point the warning at the redundant binding."""
        source = "_TIMEOUT = 30\nconnect(timeout=_TIMEOUT)\n"
        findings = check_patterns(ast.parse(source))
        assert [(node.lineno, node.col_offset, code) for node, code, _ in findings] == [(1, 0, "PY114")]

    def test_async_function(self) -> None:
        """Apply the same check to async function bodies."""
        assert codes("async def run():\n    TIMEOUT = 30\n    await connect(timeout=TIMEOUT)\n") == ["PY114"]

    def test_same_line_statement_order(self) -> None:
        """Accept later semicolon statements but not reads before the binding."""
        assert codes("_TIMEOUT = 30; connect(timeout=_TIMEOUT)\n") == ["PY114"]
        assert codes("connect(timeout=_TIMEOUT); _TIMEOUT = 30\n") == []

    def test_method_local_constant(self) -> None:
        """Distinguish method locals from class-level contracts."""
        source = "class Client:\n    def connect(self):\n        TIMEOUT = 30\n        return connect(timeout=TIMEOUT)\n"
        assert codes(source) == ["PY114"]

    def test_independent_scopes(self) -> None:
        """Do not combine unrelated constants sharing a name."""
        source = """
        def first():
            VALUE = 1
            return VALUE
        def second():
            VALUE = 2
            return VALUE
        """
        assert codes(source) == ["PY114", "PY114"]

    def test_public_class_and_exported_constants_are_preserved(self) -> None:
        """Keep externally accessible and explicitly exported contracts."""
        for source in (
            "TIMEOUT = 30\nconnect(TIMEOUT)\n",
            "class Config:\n    _TIMEOUT = 30\n    value = _TIMEOUT\n",
            '_TIMEOUT = 30\n__all__ = ["_TIMEOUT"]\nconnect(_TIMEOUT)\n',
        ):
            with self.subTest(source=source):
                assert codes(source) == []

    def test_non_candidates(self) -> None:
        """Require a single unannotated literal binding before its use."""
        for body in (
            "value = 30\nreturn value",
            "VALUE = 30\nreturn 1",
            "VALUE = 30\nreturn VALUE + VALUE",
            "VALUE = [1]\nreturn VALUE",
            "VALUE = (1, [])\nreturn VALUE",
            "VALUE = {1}\nreturn VALUE",
            'VALUE = {"key": 1}\nreturn VALUE',
            # Calls and annotations can carry behavior beyond the literal value.
            "VALUE = make_value()\nreturn VALUE",
            "VALUE = 1 + 2\nreturn VALUE",
            "VALUE: int = 30\nreturn VALUE",
            "VALUE = OTHER = 30\nreturn VALUE",
            "VALUE, = (30,)\nreturn VALUE",
            # Textual order alone cannot prove a conditional definition runs first.
            "return VALUE\nVALUE = 30",
            "if enabled:\n    VALUE = 30\nreturn VALUE",
            "VALUE = 30  # type: int\nreturn VALUE",
        ):
            with self.subTest(body=body):
                source = "def run():\n" + textwrap.indent(body, "    ")
                assert check_patterns(ast.parse(source, type_comments=True)) == []

    def test_rebinding_and_ambiguous_bindings_are_preserved(self) -> None:
        """Count non-Name bindings as well as ordinary stores and deletes."""
        for body in (
            "VALUE = 30\nVALUE = 40\nreturn VALUE",
            "VALUE = 30\nVALUE += 1\nreturn VALUE",
            "VALUE = 30\ndel VALUE\nreturn VALUE",
            "VALUE = 30\nfor VALUE in items:\n    pass\nreturn VALUE",
            "VALUE = 30\nimport other as VALUE\nreturn VALUE",
            "VALUE = 30\ndef VALUE():\n    pass\nreturn VALUE",
            "VALUE = 30\nclass VALUE:\n    pass\nreturn VALUE",
            # Exception and pattern bindings are represented as strings in the AST.
            "VALUE = 30\ntry:\n    work()\nexcept Error as VALUE:\n    pass\nreturn VALUE",
            'VALUE = 30\nmatch item:\n    case {"key": VALUE}:\n        pass\nreturn VALUE',
            "VALUE = 30\nmatch item:\n    case {**VALUE}:\n        pass\nreturn VALUE",
            "global VALUE\nVALUE = 30\nreturn VALUE",
            "nonlocal VALUE\nVALUE = 30\nreturn VALUE",
            "VALUE = 30\nreturn (VALUE := 40)",
        ):
            with self.subTest(body=body):
                assert codes("def run():\n" + textwrap.indent(body, "    ")) == []
        assert codes("def run(VALUE):\n    VALUE = 30\n    return VALUE\n") == []

    def test_nested_scopes_and_comprehensions_are_preserved(self) -> None:
        """Avoid guessing whether nested names capture or shadow the constant."""
        for body in (
            "VALUE = 30\ndef inner():\n    return VALUE\nreturn inner()",
            "VALUE = 30\nreturn lambda: VALUE",
            "VALUE = 30\nreturn [VALUE for item in items]",
            "VALUE = 30\nreturn [VALUE for VALUE in items]",
            # Class bodies and nested parameter lists introduce distinct scopes too.
            "VALUE = 30\nclass Inner:\n    value = VALUE\nreturn Inner",
            "VALUE = 30\ndef inner(VALUE):\n    pass\nreturn VALUE",
        ):
            with self.subTest(body=body):
                assert codes("def run():\n" + textwrap.indent(body, "    ")) == []
        assert codes("_VALUE = 30\ndef run():\n    return _VALUE\n") == []

    def test_dynamic_namespace_access_is_preserved(self) -> None:
        """Namespace introspection can observe otherwise invisible uses."""
        for call in ("locals()", "globals()", "vars()", 'eval("VALUE")', 'exec("VALUE = 40")'):
            with self.subTest(call=call):
                assert codes(f"def run():\n    VALUE = 30\n    {call}\n    return VALUE\n") == []


class StructuralReviewTests(unittest.TestCase):
    """Distinguish transparent wrappers from ownership and framework boundaries."""

    def test_private_transparent_wrapper(self) -> None:
        """Review exact private forwarding wrappers without added behavior."""
        assert codes("def _fetch(value):\n    return fetch(value)\n") == ["PY110"]

    def test_public_contracts_decorators_and_transformations_are_preserved(self) -> None:
        """Preserve public, typed, decorated, and transforming wrapper boundaries."""
        for source in (
            "def fetch(value):\n    return other(value)\n",
            "def _fetch(value) -> User:\n    return other(value)\n",
            "@hook\ndef _fetch(value):\n    return other(value)\n",
            "def _fetch(value):\n    return other(transform(value))\n",
        ):
            with self.subTest(source=source):
                assert codes(source) == []

    def test_empty_test_client_subclass(self) -> None:
        """Review a known test-client subclass that adds no behavior."""
        source = "from fastapi.testclient import TestClient as FastAPITestClient\nclass TestClient(FastAPITestClient):\n    pass\n"
        assert codes(source) == ["PY110"]

    def test_framework_subclass_and_documented_boundary_are_preserved(self) -> None:
        """Keep framework subclasses and intentionally documented compatibility aliases."""
        source = '''
        from unittest import TestCase
        class Tests(TestCase):
            pass
        class _Boundary(Base):
            """Public compatibility boundary."""
            pass
        '''
        assert codes(source) == ["PY016"]

    def test_private_framework_hook_is_preserved(self) -> None:
        """Retain inherited private hooks even when they only forward a call."""
        source = """
        class Handler(Framework):
            def _dispatch(self, request):
                return dispatch(self, request)
        """
        assert codes(source) == []

    def test_borrowed_client_only_class(self) -> None:
        """Review a class whose only state and behavior wrap a borrowed client."""
        source = """
        class Organizations:
            def __init__(self, client):
                self._client = client
            async def delete(self, organization_id):
                await utils.delete_namespace(await self._client.api(), organization_id)
        """
        assert codes(source) == ["PY111"]

    def test_owned_client_extra_state_and_framework_boundaries_are_preserved(self) -> None:
        """Preserve owned clients, extra instance state, and inherited contracts."""
        for source in (
            "class Client:\n    def __init__(self, config):\n        self._client = API(config)\n    def fetch(self):\n        return self._client.fetch()\n",
            "class Client:\n    def __init__(self, client):\n        self._client = client\n        self._cache = {}\n    def fetch(self):\n        return self._client.fetch()\n",
            "class Client(Interface):\n    def __init__(self, client):\n        self._client = client\n    def fetch(self):\n        return self._client.fetch()\n",
        ):
            # Assert: each ownership or inheritance boundary prevents this review.
            with self.subTest(source=source):
                assert codes(source) == []


if __name__ == "__main__":
    unittest.main()
