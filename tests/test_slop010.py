import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize("options", ["", ", default_response_class=JSONResponse"])
def test_json_routes_require_explicit_schemas(run_cli: RunCLI, options: str) -> None:
    """Neither return annotations nor default JSONResponse supply a route schema."""

    # Arrange
    source = f"from fastapi import APIRouter\nfrom starlette.responses import JSONResponse\nrouter = APIRouter()\n@router.get('/users'{options})\nasync def list_users() -> list[UserResponse]:\n    return await users.fetch()\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP010"]


EXEMPTIONS = (
    # Explicit schemas and deliberate opt-outs both satisfy the schema policy.
    pytest.param(
        "from fastapi import APIRouter as Router\nrouter = Router()\n@router.get('/users', response_model=list[UserResponse])\nasync def list_users() -> list[UserResponse]:\n    return await users.fetch()\n",
        id="explicit-response-model",
    ),
    pytest.param(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/users', response_model=None)\ndef list_users():\n    return users\n",
        id="explicit-schema-opt-out",
    ),
    # HEAD and bodyless statuses do not serialize JSON bodies.
    pytest.param(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.head('/users')\ndef head_users():\n    return None\n", id="head-route"
    ),
    pytest.param(
        "from fastapi import FastAPI, status\napp = FastAPI()\n@app.delete('/user', status_code=status.HTTP_204_NO_CONTENT)\ndef remove(status):\n    return None\n",
        id="bodyless-status-with-shadowed-parameter",
    ),
    # Raw responses and WebSockets bypass ordinary JSON serialization.
    pytest.param(
        "from fastapi import FastAPI\nfrom starlette.responses import JSONResponse as Raw\napp = FastAPI()\n@app.get('/users')\ndef list_users():\n    return Raw(content=users)\n",
        id="raw-response-return",
    ),
    pytest.param(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.websocket('/socket')\nasync def socket(websocket):\n    await websocket.accept()\n",
        id="websocket",
    ),
    # Unknown decorator options and imported router instances are not inferred.
    pytest.param(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/users', **route_options)\ndef list_users():\n    return users\n",
        id="unknown-route-options",
    ),
    pytest.param("from routes import router\n@router.get('/users')\ndef list_users():\n    return users\n", id="imported-router-instance"),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_documented_non_json_and_unknown_routes(run_cli: RunCLI, source: str) -> None:
    """Honor deliberate schemas and routes without inferred JSON contracts."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


def test_nested_json_endpoint_is_not_exempted_by_outer_raw_response(run_cli: RunCLI) -> None:
    """Keep each endpoint's raw-response exemption scoped to that endpoint."""

    # Arrange
    source = """
        from fastapi import FastAPI, Response
        app = FastAPI()
        @app.get('/outer')
        def outer():
            @app.get('/inner')
            def inner():
                return {'value': 1}
            return Response()
    """

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == ["SLOP010"]
    assert "example.py:5:6: SLOP010" in result.stdout
