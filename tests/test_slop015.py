import pytest
from tests.support import RunCLI, native_codes


def test_reports_response_model_revalidation(run_cli: RunCLI) -> None:
    """Review reconstructing the model already declared by the route."""

    # Arrange
    source = """
        from fastapi import APIRouter
        from schemas import UserResponse as Output
        router = APIRouter()
        @router.get('/user', response_model=Output)
        def get_user():
            return Output.model_validate(user)
    """

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP015"]


EXEMPTIONS = (
    pytest.param("return user", id="direct-payload"),
    pytest.param("return UserResponse.model_validate(user, from_attributes=True)", id="explicit-options"),
    pytest.param("return UserResponse.model_validate(transform(user))", id="computed-input"),
    pytest.param("return OtherResponse.model_validate(user)", id="different-model"),
)


@pytest.mark.parametrize("body", EXEMPTIONS)
def test_preserves_explicit_validation_choices(run_cli: RunCLI, body: str) -> None:
    """Do not discard validation options or intentional transformations."""

    # Arrange
    source = f"from fastapi import APIRouter\nfrom schemas import UserResponse\nrouter = APIRouter()\n@router.get('/user', response_model=UserResponse)\ndef get_user():\n    {body}\n"

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []


CONTRACTS = (
    # Protocol metadata and stacked route contracts constrain reconstruction.
    pytest.param(
        "from fastapi import FastAPI\nfrom schemas import UserResponse\napp = FastAPI()\n@app.get('/user', response_model=UserResponse, openapi_extra={'x-external-protocol': True})\ndef get_user():\n    return UserResponse.model_validate(user)\n",
        id="external-protocol",
    ),
    pytest.param(
        "from fastapi import FastAPI\nfrom schemas import UserResponse, OtherResponse\napp = FastAPI()\n@app.get('/one', response_model=UserResponse)\n@app.get('/two', response_model=OtherResponse)\ndef get_user():\n    return UserResponse.model_validate(user)\n",
        id="different-stacked-contracts",
    ),
    # Visible validators can intentionally transform the returned value.
    pytest.param(
        "from fastapi import FastAPI\nfrom pydantic import BaseModel, model_validator\nclass UserResponse(BaseModel):\n    @model_validator(mode='after')\n    def normalize(self):\n        return self\napp = FastAPI()\n@app.get('/user', response_model=UserResponse)\ndef get_user():\n    return UserResponse.model_validate(user)\n",
        id="visible-validator",
    ),
)


@pytest.mark.parametrize("source", CONTRACTS)
def test_preserves_model_and_protocol_boundaries(run_cli: RunCLI, source: str) -> None:
    """Retain reconstruction when model or route contracts can add behavior."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
