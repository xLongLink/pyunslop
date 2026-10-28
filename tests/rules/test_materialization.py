import unittest
from tests.support import codes


class MaterializationReviewTests(unittest.TestCase):
    """Limit iterable materialization reviews to conservative single-use candidates."""

    def test_direct_iterable_consumer(self) -> None:
        """Review a list comprehension consumed directly by a known iterable API."""
        assert codes("total = sum([invoice.amount for invoice in invoices])") == ["PY107"]

    def test_adjacent_single_use_temporary(self) -> None:
        """Review a temporary list consumed only by the next statement."""
        source = """
        def total(invoices):
            amounts = [invoice.amount for invoice in invoices]
            return sum(amounts)
        """
        assert codes(source) == ["PY107"]

    def test_reused_or_snapshot_lists_are_preserved(self) -> None:
        """Retain reused lists and snapshots separated from their consumer by work."""
        for body in (
            "amounts = [invoice.amount for invoice in invoices]\n    log(amounts)\n    return sum(amounts)",
            "amounts = [invoice.amount for invoice in invoices]\n    mutate(invoices)\n    return sum(amounts)",
            "amounts = [invoice.amount for invoice in invoices]\n    return mutate(invoices) + sum(amounts)",
        ):
            with self.subTest(body=body):
                assert codes("def total(invoices):\n    " + body) == []

    def test_side_effecting_and_short_circuiting_expressions_are_preserved(self) -> None:
        """Keep eager evaluation when calls or short-circuiting affect timing."""
        for expression in ("sum([load(x) for x in xs])", "any([item.flag for item in items])", "all([item.flag for item in items])"):
            with self.subTest(expression=expression):
                assert codes(expression) == []

    def test_unknown_consumers_are_ignored(self) -> None:
        """Do not assume an unknown consumer accepts lazy iterables."""
        assert codes("consume([invoice.amount for invoice in invoices])") == []

    def test_shadowed_consumers_are_preserved(self) -> None:
        """Require builtin consumer identity after parameters or assignments shadow names."""
        for prefix in ("def total(invoices, sum):\n", "def total(invoices):\n    sum = custom\n"):
            with self.subTest(prefix=prefix):
                source = prefix + "    amounts = [invoice.amount for invoice in invoices]\n    return sum(amounts)\n"
                assert codes(source) == []

    def test_closure_snapshot_is_preserved(self) -> None:
        """Count a nested closure's reference as reuse of the materialized snapshot."""
        source = """
        def total(invoices):
            amounts = [invoice.amount for invoice in invoices]
            def later():
                return amounts
            value = sum(amounts)
            return value, later
        """
        assert codes(source) == []
