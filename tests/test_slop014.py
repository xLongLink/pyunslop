import pytest
from tests.support import RunCLI, native_codes


@pytest.mark.parametrize(
    ("imported", "base"),
    [
        ("from pydantic import BaseModel", "BaseModel"),
        ("from pydantic import BaseModel as Model", "Model"),
        ("import pydantic.v1 as pd", "pd.BaseModel"),
    ],
)
def test_reports_shorter_fields_in_recognized_models(run_cli: RunCLI, imported: str, base: str) -> None:
    """Keep diagnostic coordinates tied to the out-of-order field."""

    # Arrange
    source = f"{imported}\nclass UserResponse({base}):\n    description: str\n    id: int\n"

    # Act
    result = run_cli(source)

    # Assert
    assert result.returncode == 1
    assert native_codes(result) == ["SLOP014"]
    assert "example.py:4:5: SLOP014" in result.stdout
    assert "validation dependencies" in result.stdout


def test_multiline_defaults_do_not_split_field_runs(run_cli: RunCLI) -> None:
    """Ignore blank lines inside defaults when locating section boundaries."""
    source = """
        from pydantic import BaseModel
        class UserResponse(BaseModel):
            description: str = (
                "default"

            )
            id: int
    """

    result = run_cli(source)

    assert native_codes(result) == ["SLOP014"]
    assert "example.py:7:5: SLOP014" in result.stdout


def test_recognizes_nested_models_in_unrecognized_classes(run_cli: RunCLI) -> None:
    """Traverse class bodies even when their own bases are not recognized."""
    source = """
        from pydantic import BaseModel
        class Container:
            class UserResponse(BaseModel):
                description: str
                id: int
    """

    result = run_cli(source)

    assert native_codes(result) == ["SLOP014"]
    assert "example.py:5:9: SLOP014" in result.stdout


EXEMPTIONS = (
    # Ordered fields and equal-length ties satisfy the policy.
    pytest.param(
        "from pydantic import BaseModel\nclass UserResponse(BaseModel):\n    id: int\n    description: str\n", id="ordered-fields"
    ),
    pytest.param("from pydantic import BaseModel\nclass UserResponse(BaseModel):\n    name: str\n    date: str\n", id="equal-lengths"),
    pytest.param(
        "from pydantic import BaseModel\nclass UserResponse(BaseModel):\n    description: str\n\n    id: int\n", id="blank-line-section"
    ),
    # Methods, private attributes, and ClassVars split field runs.
    pytest.param(
        "from pydantic import BaseModel\nclass UserResponse(BaseModel):\n    description: str\n    def method(self):\n        pass\n    id: int\n",
        id="method-boundary",
    ),
    pytest.param(
        "from pydantic import BaseModel\nclass UserResponse(BaseModel):\n    description: str\n    _private: str\n    id: int\n",
        id="private-state-boundary",
    ),
    # ClassVars are excluded by their resolved annotation identity.
    pytest.param(
        "from typing import ClassVar as CV\nfrom pydantic import BaseModel\nclass UserResponse(BaseModel):\n    description: str\n    setting: CV[int]\n    id: int\n",
        id="classvar-boundary",
    ),
    # Configuration and indirect inheritance do not extend a recognized field run.
    pytest.param(
        "from pydantic import BaseModel\nclass UserResponse(BaseModel):\n    description: str\n    model_config: dict = {}\n    id: int\n",
        id="configuration-boundary",
    ),
    pytest.param(
        "from pydantic import BaseModel\nclass Parent(BaseModel):\n    id: int\nclass Child(Parent):\n    description: str\n    id: int\n",
        id="indirect-base",
    ),
)


@pytest.mark.parametrize("source", EXEMPTIONS)
def test_preserves_sections_and_nonfield_boundaries(run_cli: RunCLI, source: str) -> None:
    """Apply field-length ordering only within directly recognized field runs."""

    # Act
    result = run_cli(source)

    # Assert
    assert native_codes(result) == []
