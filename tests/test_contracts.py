import ast
from pyunslop.contracts import LoopNode, WithNode, FunctionNode


def test_async_nodes_share_their_synchronous_contracts() -> None:
    """Shared visitors must accept both forms of functions, loops, and contexts."""

    # Arrange
    tree = ast.parse(
        "def sync():\n    for item in items:\n        with manager:\n            pass\nasync def asynchronous():\n    async for item in items:\n        async with manager:\n            pass\n"
    )
    sync, asynchronous = tree.body

    # Act
    functions = [node for node in tree.body if isinstance(node, FunctionNode)]
    loops = [node for node in ast.walk(tree) if isinstance(node, LoopNode)]
    contexts = [node for node in ast.walk(tree) if isinstance(node, WithNode)]

    # Assert
    assert functions == [sync, asynchronous]
    assert loops == [sync.body[0], asynchronous.body[0]]
    assert contexts == [sync.body[0].body[0], asynchronous.body[0].body[0]]
