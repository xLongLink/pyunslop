import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize(
    "body",
    ["return {'success': True, 'detail': 'Users fetched', 'data': users}", "payload = dict(success=True, data=users)\n    return payload"],
)
def test_reports_generic_endpoint_envelopes(run_cli: RunCLI, body: str) -> None:
    """Check direct and locally assigned envelopes even with response_model=None."""

    # Arrange
    source = (
        f"from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/users', response_model=None)\ndef list_users():\n    {body}\n"
    )

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP011"]


EXEMPTIONS = (
    # Direct payloads and explicit failures are not generic success wrappers.
    pytest.param(
        "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/users', response_model=list[UserResponse])\nasync def list_users():\n    return await users.fetch()\n",
        id="direct-payload",
    ),
    pytest.param(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/status', response_model=None)\ndef status():\n    return {'success': False, 'detail': 'Failed'}\n",
        id="failure-payload",
    ),
    # Ordinary functions and explicit protocols retain their own contracts.
    pytest.param("def protocol():\n    return {'success': True, 'data': users}\n", id="non-route-function"),
    pytest.param(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/protocol', response_model=None, openapi_extra={'x-external-protocol': True})\ndef protocol():\n    return {'success': True, 'data': users}\n",
        id="external-protocol",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_payloads_and_explicit_external_contracts(run_cli: RunCLI, source: str) -> None:
    """Avoid treating ordinary functions or protocol contracts as API wrappers."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
