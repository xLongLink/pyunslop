# SLOP006: Read-only query return contracts

Use `Sequence[T]` rather than `list[T]` or `typing.List[T]` when directly
returning recognized query rows, including rows wrapped in `list()`. Ordinary
functions that build mutable lists are ignored. Preserve a list contract when
callers intentionally require mutability; this warning does not prove otherwise.

```py
# Bad
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch(session: AsyncSession) -> list[User]:
    result = await session.scalars(statement)
    return result.all()

# Good
from collections.abc import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch(session: AsyncSession) -> Sequence[User]:
    result = await session.scalars(statement)
    return result.all()
```
