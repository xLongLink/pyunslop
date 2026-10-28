import ast
import textwrap
import unittest

from pyunslop.analysis import check_patterns


def codes(source: str) -> list[str]:
    return [code for _, code, _ in check_patterns(ast.parse(textwrap.dedent(source)))]


class BufferedIterationTests(unittest.TestCase):
    def test_buffered_async_execute_and_scalars(self) -> None:
        for method in ("execute", "scalars"):
            with self.subTest(method=method):
                source = f"from sqlalchemy.ext.asyncio import AsyncSession\nasync def fetch(s: AsyncSession):\n    result = await s.{method}(stmt)\n    for row in result.all():\n        consume(row)\n"
                self.assertEqual(codes(source), ["PY004"])

    def test_buffered_result_annotations_and_transforms(self) -> None:
        for result_type in ("Result", "ScalarResult", "MappingResult", "CursorResult"):
            with self.subTest(result_type=result_type):
                source = f"from sqlalchemy.engine import {result_type} as Rows\ndef consume(result: Rows):\n    for row in result.unique().all():\n        use(row)\n"
                self.assertEqual(codes(source), ["PY004"])

    def test_streaming_and_unknown_results_are_ignored(self) -> None:
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
        self.assertEqual(codes(source), [])

    def test_yield_per_and_async_iteration_are_ignored(self) -> None:
        source = """
        from sqlalchemy.engine import Result
        async def fetch(result: Result):
            for row in result.yield_per(100).all():
                consume(row)
            async for row in result.all():
                consume(row)
        """
        self.assertEqual(codes(source), [])

    def test_materialization_used_elsewhere_is_ignored(self) -> None:
        source = """
        from sqlalchemy.engine import Result
        def fetch(result: Result):
            rows = result.all()
            for row in rows:
                consume(row)
            for row in reversed(result.all()):
                consume(row)
        """
        self.assertEqual(codes(source), [])


class InComprehensionTests(unittest.TestCase):
    def test_sqlmodel_col_and_import_aliases(self) -> None:
        source = """
        from sqlmodel import col as column
        statement = column(User.id).in_([member.user_id for member in members])
        """
        self.assertEqual(codes(source), ["PY005"])

    def test_sqlalchemy_column(self) -> None:
        source = """
        import sqlalchemy as sa
        expression = sa.column('id').in_([item.id for item in items])
        """
        self.assertEqual(codes(source), ["PY005"])

    def test_select_where_context(self) -> None:
        source = """
        from sqlalchemy import select
        statement = select(User)
        statement = statement.where(User.id.in_([item.id for item in items]))
        """
        self.assertEqual(codes(source), ["PY005"])

    def test_generator_and_reused_list_are_allowed(self) -> None:
        source = """
        from sqlmodel import col
        ids = [member.user_id for member in members]
        first = col(User.id).in_(ids)
        second = col(User.id).in_(member.user_id for member in members)
        """
        self.assertEqual(codes(source), [])

    def test_unrelated_in_method_is_ignored(self) -> None:
        source = """
        from sqlalchemy import select
        custom.in_([member.id for member in members])
        statement = select(User).where(custom.consume(custom.in_([item.id for item in items])))
        """
        self.assertEqual(codes(source), [])


class NamedDomainInstanceTests(unittest.TestCase):
    def test_allowlisted_classes(self) -> None:
        source = """
        async def fetch():
            usage = await Postgres(host, port).usage()
            logs = await Kubernetes(config).applications.logs(name)
        """
        self.assertEqual(codes(source), ["PY006", "PY006"])

    def test_import_aliases_and_module_qualified_classes(self) -> None:
        source = """
        from domain import Postgres as Database
        import domain as d
        usage = Database(host).usage()
        logs = d.Kubernetes(config).applications.logs(name)
        """
        self.assertEqual(codes(source), ["PY006", "PY006"])

    def test_named_instances_and_other_classes_are_allowed(self) -> None:
        source = """
        database = Postgres(host)
        usage = database.usage()
        logs = OtherClient(config).applications.logs(name)
        """
        self.assertEqual(codes(source), [])

    def test_allowlisted_local_class(self) -> None:
        source = """
        class Postgres:
            pass
        usage = Postgres(host).usage()
        """
        self.assertEqual(codes(source), ["PY006"])

    def test_shadowed_alias_is_ignored(self) -> None:
        source = """
        from domain import Postgres as Database
        def fetch(Database):
            return Database(host).usage()
        """
        self.assertEqual(codes(source), [])


class ApiSchemaTests(unittest.TestCase):
    def test_json_endpoint_requires_explicit_schema(self) -> None:
        source = """
        from fastapi import APIRouter
        router = APIRouter()
        @router.get('/users')
        async def users() -> list[UserResponse]:
            return fetch_users()
        """
        self.assertEqual(codes(source), ["PY009"])

    def test_explicit_schema_or_none_is_allowed(self) -> None:
        for model in ("list[UserResponse]", "None"):
            with self.subTest(model=model):
                source = f"from fastapi import FastAPI as App\napp = App()\n@app.get('/users', response_model={model})\ndef users():\n    return fetch_users()\n"
                self.assertEqual(codes(source), [])

    def test_bodyless_status_exemptions(self) -> None:
        for status in ("204", "205", "304", "status.HTTP_204_NO_CONTENT"):
            with self.subTest(status=status):
                source = f"from fastapi import FastAPI, status\napp = FastAPI()\n@app.delete('/user', status_code={status})\ndef remove_user():\n    return None\n"
                self.assertEqual(codes(source), [])

    def test_head_and_websocket_exemptions(self) -> None:
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
        self.assertEqual(codes(source), [])

    def test_status_alias_is_resolved_outside_parameter_scope(self) -> None:
        source = """
        from fastapi import FastAPI, status
        app = FastAPI()
        @app.delete('/user', status_code=status.HTTP_204_NO_CONTENT)
        def remove(status):
            return None
        """
        self.assertEqual(codes(source), [])

    def test_standard_library_bodyless_status(self) -> None:
        source = """
        from fastapi import FastAPI
        from http import HTTPStatus
        app = FastAPI()
        @app.delete('/user', status_code=HTTPStatus.NO_CONTENT)
        def remove():
            return None
        """
        self.assertEqual(codes(source), [])

    def test_stream_redirect_and_raw_response_classes(self) -> None:
        for response in ("Response", "StreamingResponse", "RedirectResponse", "FileResponse", "HTMLResponse"):
            with self.subTest(response=response):
                source = f"from fastapi import FastAPI\nfrom fastapi.responses import {response}\napp = FastAPI()\n@app.get('/', response_class={response})\ndef endpoint():\n    return payload\n"
                self.assertEqual(codes(source), [])

    def test_default_json_response_class_still_requires_model(self) -> None:
        source = """
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        app = FastAPI()
        @app.get('/', response_class=JSONResponse)
        def endpoint():
            return payload
        """
        self.assertEqual(codes(source), ["PY009"])

    def test_raw_response_annotation_or_return(self) -> None:
        for body in (
            "def endpoint() -> Raw:\n    return make_response()",
            "def endpoint():\n    return Raw(content=payload)",
            "def endpoint():\n    response = Raw(content=payload)\n    return response",
        ):
            with self.subTest(body=body):
                source = "from fastapi import APIRouter\nfrom starlette.responses import JSONResponse as Raw\nrouter = APIRouter()\n@router.get('/')\n" + body
                self.assertEqual(codes(source), [])

    def test_mixed_raw_and_json_returns_require_schema(self) -> None:
        source = """
        from fastapi import FastAPI, Response
        app = FastAPI()
        @app.get('/')
        def endpoint():
            if condition:
                return Response()
            return {'users': users}
        """
        self.assertEqual(codes(source), ["PY009"])

    def test_unrelated_router_is_ignored(self) -> None:
        source = """
        from other_framework import Router
        router = Router()
        @router.get('/')
        def endpoint():
            return {'success': True, 'data': users}
        """
        self.assertEqual(codes(source), [])


class ApiEnvelopeTests(unittest.TestCase):
    def test_success_envelope_return(self) -> None:
        source = """
        from fastapi import APIRouter
        router = APIRouter()
        @router.get('/users', response_model=UserResponse)
        async def users():
            return {'success': True, 'detail': 'Users fetched', 'data': users}
        """
        self.assertEqual(codes(source), ["PY010"])

    def test_named_and_dict_constructor_envelopes(self) -> None:
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/', response_model=UserResponse)
        def endpoint():
            payload = dict(success=True, data=users)
            return payload
        """
        self.assertEqual(codes(source), ["PY010"])

    def test_payloads_and_non_api_functions_are_ignored(self) -> None:
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
        self.assertEqual(codes(source), [])

    def test_external_protocol_exemptions(self) -> None:
        for option in (
            "response_model=None, openapi_extra={'x-external-protocol': True}",
            "response_model=ProtocolResponse, openapi_extra={'x-external-protocol': True}",
        ):
            with self.subTest(option=option):
                source = f"from fastapi import FastAPI\napp = FastAPI()\n@app.post('/protocol', {option})\ndef endpoint():\n    return {{'success': True, 'detail': 'OK', 'data': payload}}\n"
                self.assertEqual(codes(source), [])

    def test_none_schema_is_not_an_external_protocol_marker(self) -> None:
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/', response_model=None)
        def endpoint():
            return {'success': True, 'data': users}
        """
        self.assertEqual(codes(source), ["PY010"])

    def test_nested_non_route_return_is_not_an_api_return(self) -> None:
        source = """
        from fastapi import FastAPI
        app = FastAPI()
        @app.get('/', response_model=UserResponse)
        def endpoint():
            def helper():
                return {'success': True, 'data': users}
            return users
        """
        self.assertEqual(codes(source), [])


if __name__ == "__main__":
    unittest.main()
