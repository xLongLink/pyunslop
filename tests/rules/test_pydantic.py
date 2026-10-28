import ast
import textwrap
import unittest
from tests.support import codes, check_patterns


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
