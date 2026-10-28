import pytest
from tests.support import codes

RAW_RESPONSE_CLASSES = ("Response", "StreamingResponse", "RedirectResponse", "FileResponse", "HTMLResponse")


@pytest.mark.parametrize("status", ["204", "205", "304", "status.HTTP_204_NO_CONTENT"])
def test_bodyless_status_exemptions(status: str) -> None:
    """Exempt literal and symbolic statuses that intentionally have no body."""
    source = f"from fastapi import FastAPI, status\napp = FastAPI()\n@app.delete('/user', status_code={status})\ndef remove_user():\n    return None\n"
    assert codes(source) == []


def test_head_and_websocket_exemptions() -> None:
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


def test_standard_library_bodyless_status() -> None:
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


@pytest.mark.parametrize("response", RAW_RESPONSE_CLASSES)
def test_stream_redirect_and_raw_response_classes(response: str) -> None:
    """Exempt explicitly selected streaming, redirect, and raw response classes."""
    source = f"from fastapi import FastAPI\nfrom fastapi.responses import {response}\napp = FastAPI()\n@app.get('/', response_class={response})\ndef endpoint():\n    return payload\n"
    assert codes(source) == []


def test_default_json_response_class_still_requires_model() -> None:
    """Do not mistake the ordinary JSON response class for a declared schema."""
    source = """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    @app.get('/', response_class=JSONResponse)
    def endpoint():
        return payload
    """
    assert codes(source) == ["SLOP011"]
