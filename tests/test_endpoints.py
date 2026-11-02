import ast
import pytest
from pyunslop.analysis.endpoints import EndpointAnalyzer


@pytest.mark.parametrize(
    ("source", "expression", "annotation_kind", "constructor_kind"),
    [
        ("from fastapi import APIRouter as Router", "Router", "@router", "@router"),
        ("import fastapi as api", "api.FastAPI", "@router", "@router"),
        ("from fastapi.routing import APIRouter as Router", "Router[Item]", "@router", ""),
        ("from fastapi.applications import FastAPI as App", "'App[Item]'", "@router", ""),
        ("from fastapi import APIRouter as Router\nRouter = factory", "Router", "", ""),
        ("from starlette.responses import JSONResponse as Raw", "Raw", "@response", "@response"),
        ("import fastapi.responses as responses", "responses.Response", "@response", "@response"),
        ("from fastapi import Response as Raw", "Raw[Item]", "@response", ""),
        ("from fastapi import Response as Raw", "'Raw[Item]'", "@response", ""),
        ("from fastapi import Response as Raw\nRaw = factory", "Raw", "", ""),
        ("from custom import APIRouter", "APIRouter", "", ""),
        ("", "factory().Response", "", ""),
    ],
)
def test_annotation_and_constructor_classification(source: str, expression: str, annotation_kind: str, constructor_kind: str) -> None:
    """Share identity classification without unwrapping constructor expressions."""
    analyzer = EndpointAnalyzer()

    # Act
    analyzer.visit(ast.parse(f"{source}\nannotated: {expression}\nconstructed = {expression}()"))

    # Assert
    assert analyzer.kind(ast.Name(id="annotated")) == annotation_kind
    assert analyzer.kind(ast.Name(id="constructed")) == constructor_kind


def test_success_envelope_call_precedes_constructor_classification() -> None:
    """Recognize dict envelopes before handling ordinary constructor calls."""
    analyzer = EndpointAnalyzer()

    # Act
    kind = analyzer.kind(ast.parse("dict(success=True, data=payload)", mode="eval").body)

    # Assert
    assert kind == "@envelope"
