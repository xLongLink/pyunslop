import pytest
from tests.support import codes

SNAPSHOT_CONSUMERS = (
    "amounts = [invoice.amount for invoice in invoices]\n    log(amounts)\n    return sum(amounts)",
    "amounts = [invoice.amount for invoice in invoices]\n    mutate(invoices)\n    return sum(amounts)",
    "amounts = [invoice.amount for invoice in invoices]\n    return mutate(invoices) + sum(amounts)",
)


EAGER_EXPRESSIONS = ("sum([load(x) for x in xs])", "any([item.flag for item in items])", "all([item.flag for item in items])")


def test_direct_iterable_consumer() -> None:
    """Review a list comprehension consumed directly by a known iterable API."""
    assert codes("total = sum([invoice.amount for invoice in invoices])") == ["SLOP018"]


def test_adjacent_single_use_temporary() -> None:
    """Review a temporary list consumed only by the next statement."""
    source = """
    def total(invoices):
        amounts = [invoice.amount for invoice in invoices]
        return sum(amounts)
    """
    assert codes(source) == ["SLOP018"]


@pytest.mark.parametrize("body", SNAPSHOT_CONSUMERS)
def test_reused_or_snapshot_lists_are_preserved(body: str) -> None:
    """Retain reused lists and snapshots separated from their consumer by work."""
    assert codes("def total(invoices):\n    " + body) == []


@pytest.mark.parametrize("expression", EAGER_EXPRESSIONS)
def test_side_effecting_and_short_circuiting_expressions_are_preserved(expression: str) -> None:
    """Keep eager evaluation when calls or short-circuiting affect timing."""
    assert codes(expression) == []


def test_unknown_consumers_are_ignored() -> None:
    """Do not assume an unknown consumer accepts lazy iterables."""
    assert codes("consume([invoice.amount for invoice in invoices])") == []


@pytest.mark.parametrize("prefix", ["def total(invoices, sum):\n", "def total(invoices):\n    sum = custom\n"])
def test_shadowed_consumers_are_preserved(prefix: str) -> None:
    """Require builtin consumer identity after parameters or assignments shadow names."""
    source = prefix + "    amounts = [invoice.amount for invoice in invoices]\n    return sum(amounts)\n"
    assert codes(source) == []


def test_closure_snapshot_is_preserved() -> None:
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
