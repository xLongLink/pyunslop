# SLOP018: Prefer scalar query APIs

Review known `execute(...).scalars()` consumption and one-element row unpacking
from syntactically single-selection queries. Prefer `session.scalars()` while
preserving the original `one`, `one_or_none`, or other cardinality and null
handling. Multi-column unpacking and unknown selection shapes are not simplified.
This is a review candidate, not an automatic query rewrite.

```py
# Bad
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch(session: AsyncSession):
    result = await session.execute(statement)
    return result.scalars().one_or_none()

# Good
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch(session: AsyncSession):
    result = await session.scalars(statement)
    return result.one_or_none()
```
