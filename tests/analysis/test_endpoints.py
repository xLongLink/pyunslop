import ast
import textwrap
import unittest
from tests.support import codes, check_patterns


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


class EndpointStateTests(unittest.TestCase):
    """Keep model and raw-response exemptions within their owning scopes."""

    def test_response_model_exemptions_do_not_leak(self) -> None:
        """A transforming model in one file must not exempt another file's model."""

        # Arrange
        route = "\nfrom fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/', response_model=Model)\ndef fetch():\n    return Model.model_validate(value)"
        transforming = "class Model:\n    def model_post_init(self): pass\n"

        # Act
        exempt = check_patterns(ast.parse(transforming + route))
        findings = check_patterns(ast.parse(route))

        # Assert
        assert exempt == []
        assert [finding.code for finding in findings] == ["PY101"]

    def test_raw_returns_belong_to_their_function(self) -> None:
        """An enclosing raw-response endpoint must not exempt a nested JSON endpoint."""

        # Arrange
        source = textwrap.dedent("""
        from fastapi import APIRouter, Response
        router = APIRouter()
        @router.get('/outer')
        def outer():
            @router.get('/inner')
            def inner():
                return {'value': 1}
            return Response()
        """)

        # Act
        findings = check_patterns(ast.parse(source))

        # Assert
        assert [(finding.line, finding.code) for finding in findings] == [(6, "PY009")]


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
