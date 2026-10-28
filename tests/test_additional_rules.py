import ast
import textwrap
import unittest
from test_support import check_patterns


def codes(source: str) -> list[str]:
    """Return native warning codes for a dedented source fixture."""
    return [finding.code for finding in check_patterns(ast.parse(textwrap.dedent(source)))]


class ModelFieldOrderTests(unittest.TestCase):
    """Check field-name lengths without imposing alphabetical tie-breaking."""

    def test_journal_fields_and_equal_lengths_are_accepted(self) -> None:
        """Accept the requested model and either ordering of equal-length names."""
        source = """
        from pydantic import BaseModel
        class JournalRead(BaseModel):
            # Each row represents equal debit and credit amounts.
            id: int
            date: date
            debit: str
            credit: str
            amount: int
            reason: str
            created_id: UUID
            created_at: datetime
            payment_id: int | None
            document_id: int
            reversal_of: int | None
        """
        assert codes(source) == []

    def test_import_aliases_and_warning_location(self) -> None:
        """Locate a shorter field for each supported Pydantic import spelling."""
        for imported, base in (
            ("from pydantic import BaseModel", "BaseModel"),
            ("from pydantic import BaseModel as Model", "Model"),
            ("import pydantic as pd", "pd.BaseModel"),
            ("from pydantic.main import BaseModel", "BaseModel"),
            ("from pydantic.v1 import BaseModel", "BaseModel"),
            ("import pydantic.v1 as pd", "pd.BaseModel"),
        ):
            # Resolve import provenance without requiring Pydantic at runtime.
            with self.subTest(imported=imported):
                source = f"{imported}\nclass Read({base}):\n    description: str\n    id: int\n"
                (finding,) = check_patterns(ast.parse(source), source)
                assert (finding.line, finding.column, finding.code) == (4, 5, "PY017")
                assert "validation dependencies" in finding.message

    def test_blank_lines_divide_sections_but_comments_do_not(self) -> None:
        """Reset at blank lines, not ordinary comments or multiline defaults."""
        source = textwrap.dedent("""
        from pydantic import BaseModel
        class Read(BaseModel):
            description: str

            id: int
            longer: str = Field(

                default="value",
            )
            # This comment does not start a new section.
            date: str
        """)
        findings = check_patterns(ast.parse(source), source)
        assert [finding.code for finding in findings] == ["PY017"]
        assert (findings[0].line, findings[0].column) == (12, 5)
        assert source.splitlines()[findings[0].line - 1].strip() == "date: str"

    def test_non_fields_divide_runs(self) -> None:
        """Ignore private attributes, ClassVars, configuration, and methods."""
        source = """
        from typing import ClassVar as CV
        from pydantic import BaseModel
        class Read(BaseModel):
            description: str
            _private: str
            id: int
            description: str
            setting: CV[int]
            id: int
            description: str
            model_config: dict = {}
            id: int
            description: str
            def method(self):
                pass
            id: int
        """
        assert codes(source) == []

    def test_unknown_and_shadowed_bases_are_ignored(self) -> None:
        """Do not infer model identity from a class name or indirect inheritance."""
        source = """
        class BaseModel:
            pass
        class Read(BaseModel):
            description: str
            id: int
        from pydantic import BaseModel as Model
        class Parent(Model):
            id: int
        class Child(Parent):
            description: str
            id: int
        Model = other
        class Unknown(Model):
            description: str
            id: int
        """
        assert codes(source) == []


class BufferedIterationTests(unittest.TestCase):
    """Distinguish buffered query iteration from streaming and reused materialization."""

    def test_buffered_async_execute_and_scalars(self) -> None:
        """Avoid all() when buffered async-query results are consumed only by a loop."""
        for method in ("execute", "scalars"):
            with self.subTest(method=method):
                source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(s: AsyncSession):\n    result = await s.{method}(stmt)\n    for row in result.all():\n        consume(row)\n"
                assert codes(source) == ["PY004"]

    def test_buffered_result_annotations_and_transforms(self) -> None:
        """Retain buffering knowledge through known result annotations and transforms."""
        for result_type in ("Result", "ScalarResult", "MappingResult", "CursorResult"):
            with self.subTest(result_type=result_type):
                source = f"from sqlalchemy.engine import {result_type} as Rows\ndef consume(result: Rows):\n    for row in result.unique().all():\n        use(row)\n"
                assert codes(source) == ["PY004"]

    def test_streaming_and_unknown_results_are_ignored(self) -> None:
        """Preserve materialization for streaming or unrecognized result types."""
        source = """
        from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult
        async def fetch(s: AsyncSession, async_result: AsyncResult, unknown):
            result = await s.stream(stmt)
            for row in result.all():
                consume(row)
            for row in async_result.all():
                consume(row)
            for row in unknown.all():
                consume(row)
        """
        assert codes(source) == []

    def test_yield_per_and_async_iteration_are_ignored(self) -> None:
        """Leave batching and asynchronous iteration semantics unchanged."""
        source = """
        from sqlalchemy.engine import Result
        async def fetch(result: Result):
            for row in result.yield_per(100).all():
                consume(row)
            async for row in result.all():
                consume(row)
        """
        assert codes(source) == []

    def test_materialization_used_elsewhere_is_ignored(self) -> None:
        """Preserve row lists reused or consumed by operations beyond direct iteration."""
        source = """
        from sqlalchemy.engine import Result
        def fetch(result: Result):
            rows = result.all()
            for row in rows:
                consume(row)
            for row in reversed(result.all()):
                consume(row)
        """
        assert codes(source) == []


class InComprehensionTests(unittest.TestCase):
    """Limit generator recommendations to recognized SQL expression contexts."""

    def test_sqlmodel_col_and_import_aliases(self) -> None:
        """Recognize SQLModel column helpers imported under aliases."""
        source = """
        from sqlmodel import col as column
        statement = column(User.id).in_([member.user_id for member in members])
        """
        assert codes(source) == ["PY005"]

    def test_sqlalchemy_column(self) -> None:
        """Recognize module-qualified SQLAlchemy column expressions."""
        source = """
        import sqlalchemy as sa
        expression = sa.column('id').in_([item.id for item in items])
        """
        assert codes(source) == ["PY005"]

    def test_select_where_context(self) -> None:
        """Infer SQL expression ownership inside a known select statement."""
        source = """
        from sqlalchemy import select
        statement = select(User)
        statement = statement.where(User.id.in_([item.id for item in items]))
        """
        assert codes(source) == ["PY005"]

    def test_generator_and_reused_list_are_allowed(self) -> None:
        """Accept existing generators and lists assigned outside the in_ call."""
        source = """
        from sqlmodel import col
        ids = [member.user_id for member in members]
        first = col(User.id).in_(ids)
        second = col(User.id).in_(member.user_id for member in members)
        """
        assert codes(source) == []

    def test_unrelated_in_method_is_ignored(self) -> None:
        """Avoid inferring SQL semantics through unrelated method calls."""
        source = """
        from sqlalchemy import select
        custom.in_([member.id for member in members])
        statement = select(User).where(custom.consume(custom.in_([item.id for item in items])))
        """
        assert codes(source) == []


class NamedDomainInstanceTests(unittest.TestCase):
    """Check the explicit domain-class allowlist and constructor provenance."""

    def test_allowlisted_classes(self) -> None:
        """Require names for direct and property-chained domain method calls."""
        source = """
        async def fetch():
            usage = await Postgres(host, port).usage()
            logs = await Kubernetes(config).applications.logs(name)
        """
        assert codes(source) == ["PY006", "PY006"]

    def test_import_aliases_and_module_qualified_classes(self) -> None:
        """Resolve allowlisted constructors through import aliases and modules."""
        source = """
        from domain import Postgres as Database
        import domain as d
        usage = Database(host).usage()
        logs = d.Kubernetes(config).applications.logs(name)
        """
        assert codes(source) == ["PY006", "PY006"]

    def test_named_instances_and_other_classes_are_allowed(self) -> None:
        """Allow named instances and fluent APIs outside the class allowlist."""
        source = """
        database = Postgres(host)
        usage = database.usage()
        logs = OtherClient(config).applications.logs(name)
        """
        assert codes(source) == []

    def test_allowlisted_local_class(self) -> None:
        """Apply the explicit allowlist to locally declared domain classes."""
        source = """
        class Postgres:
            pass
        usage = Postgres(host).usage()
        """
        assert codes(source) == ["PY006"]

    def test_shadowed_alias_is_ignored(self) -> None:
        """Forget an imported class alias when a parameter shadows it."""
        source = """
        from domain import Postgres as Database
        def fetch(Database):
            return Database(host).usage()
        """
        assert codes(source) == []


class ApiSchemaTests(unittest.TestCase):
    """Check JSON schema requirements and deliberate HTTP response exemptions."""

    def test_json_endpoint_requires_explicit_schema(self) -> None:
        """Require a route schema even when a function already has a return annotation."""
        source = """
        from fastapi import APIRouter
        router = APIRouter()
        @router.get('/users')
        async def users() -> list[UserResponse]:
            return fetch_users()
        """
        assert codes(source) == ["PY009"]

    def test_explicit_schema_or_none_is_allowed(self) -> None:
        """Accept an explicit response model or deliberate schema opt-out."""
        for model in ("list[UserResponse]", "None"):
            with self.subTest(model=model):
                source = f"from fastapi import FastAPI as App\napp = App()\n@app.get('/users', response_model={model})\ndef users():\n    return fetch_users()\n"
                assert codes(source) == []

    def test_bodyless_status_exemptions(self) -> None:
        """Exempt literal and symbolic statuses that intentionally have no body."""
        for status in ("204", "205", "304", "status.HTTP_204_NO_CONTENT"):
            with self.subTest(status=status):
                source = f"from fastapi import FastAPI, status\napp = FastAPI()\n@app.delete('/user', status_code={status})\ndef remove_user():\n    return None\n"
                assert codes(source) == []

    def test_head_and_websocket_exemptions(self) -> None:
        """Exclude HEAD-only routes and non-HTTP WebSocket handlers."""
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.head('/users')
        def users():
            pass
        @app.websocket('/ws')
        async def socket(ws):
            pass
        @app.api_route('/probe', methods=['HEAD'])
        def probe():
            pass
        """
        assert codes(source) == []

    def test_status_alias_is_resolved_outside_parameter_scope(self) -> None:
        """Resolve decorator options before parameter-local names can shadow imports."""
        source = """
        from fastapi import FastAPI, status
        app = FastAPI()
        @app.delete('/user', status_code=status.HTTP_204_NO_CONTENT)
        def remove(status):
            return None
        """
        assert codes(source) == []

    def test_standard_library_bodyless_status(self) -> None:
        """Recognize standard-library HTTPStatus members for bodyless responses."""
        source = """
        from fastapi import FastAPI
        from http import HTTPStatus
        app = FastAPI()
        @app.delete('/user', status_code=HTTPStatus.NO_CONTENT)
        def remove():
            return None
        """
        assert codes(source) == []

    def test_stream_redirect_and_raw_response_classes(self) -> None:
        """Exempt explicitly selected streaming, redirect, and raw response classes."""
        for response in ("Response", "StreamingResponse", "RedirectResponse", "FileResponse", "HTMLResponse"):
            with self.subTest(response=response):
                source = f"from fastapi import FastAPI\nfrom fastapi.responses import {response}\napp = FastAPI()\n@app.get('/', response_class={response})\ndef endpoint():\n    return payload\n"
                assert codes(source) == []

    def test_default_json_response_class_still_requires_model(self) -> None:
        """Do not mistake the ordinary JSON response class for a declared schema."""
        source = """
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        app = FastAPI()
        @app.get('/', response_class=JSONResponse)
        def endpoint():
            return payload
        """
        assert codes(source) == ["PY009"]

    def test_raw_response_annotation_or_return(self) -> None:
        """Exempt known raw response annotations and locally constructed instances."""
        for body in (
            "def endpoint() -> Raw:\n    return make_response()",
            "def endpoint():\n    return Raw(content=payload)",
            "def endpoint():\n    response = Raw(content=payload)\n    return response",
        ):
            with self.subTest(body=body):
                # Act / Assert: each return form must retain the same raw-response exemption.
                source = (
                    "from fastapi import APIRouter\nfrom starlette.responses import JSONResponse as Raw\nrouter = APIRouter()\n@router.get('/')\n"
                    + body
                )
                assert codes(source) == []

    def test_mixed_raw_and_json_returns_require_schema(self) -> None:
        """Require schemas when at least one endpoint branch returns ordinary JSON."""
        source = """
        from fastapi import FastAPI, Response
        app = FastAPI()
        @app.get('/')
        def endpoint():
            if condition:
                return Response()
            return {'users': users}
        """
        assert codes(source) == ["PY009"]

    def test_unrelated_router_is_ignored(self) -> None:
        """Avoid applying FastAPI policies to another framework's router."""
        source = """
        from other_framework import Router
        router = Router()
        @router.get('/')
        def endpoint():
            return {'success': True, 'data': users}
        """
        assert codes(source) == []


class ApiEnvelopeTests(unittest.TestCase):
    """Review generic success envelopes without altering external contracts."""

    def test_success_envelope_return(self) -> None:
        """Flag direct success/detail/data wrappers in ordinary API returns."""
        source = """
        from fastapi import APIRouter
        router = APIRouter()
        @router.get('/users', response_model=UserResponse)
        async def users():
            return {'success': True, 'detail': 'Users fetched', 'data': users}
        """
        assert codes(source) == ["PY010"]

    def test_named_and_dict_constructor_envelopes(self) -> None:
        """Track locally assigned envelopes created with the dict constructor."""
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/', response_model=UserResponse)
        def endpoint():
            payload = dict(success=True, data=users)
            return payload
        """
        assert codes(source) == ["PY010"]

    def test_payloads_and_non_api_functions_are_ignored(self) -> None:
        """Preserve plain payloads, failure details, and non-route functions."""
        source = """
        from fastapi import APIRouter
        router = APIRouter()
        def protocol():
            return {'success': True, 'detail': 'External', 'data': users}
        @router.get('/users', response_model=UserResponse)
        def users():
            return users
        @router.get('/status', response_model=StatusResponse)
        def status():
            return {'success': False, 'detail': 'Failed'}
        """
        assert codes(source) == []

    def test_external_protocol_exemptions(self) -> None:
        """Honor explicit external-protocol metadata regardless of schema choice."""
        for option in (
            "response_model=None, openapi_extra={'x-external-protocol': True}",
            "response_model=ProtocolResponse, openapi_extra={'x-external-protocol': True}",
        ):
            with self.subTest(option=option):
                source = f"from fastapi import FastAPI\napp = FastAPI()\n@app.post('/protocol', {option})\ndef endpoint():\n    return {{'success': True, 'detail': 'OK', 'data': payload}}\n"
                assert codes(source) == []

    def test_none_schema_is_not_an_external_protocol_marker(self) -> None:
        """Keep envelope checks active when only the response schema is disabled."""
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/', response_model=None)
        def endpoint():
            return {'success': True, 'data': users}
        """
        assert codes(source) == ["PY010"]

    def test_nested_non_route_return_is_not_an_api_return(self) -> None:
        """Avoid treating a nested helper's envelope as the endpoint return."""
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/', response_model=UserResponse)
        def endpoint():
            def helper():
                return {'success': True, 'data': users}
            return users
        """
        assert codes(source) == []


if __name__ == "__main__":
    unittest.main()
