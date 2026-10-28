# SLOP005: Name asynchronous query results

Assign an awaited SQLAlchemy or SQLModel query result before consuming it.
Recognition requires known imports, annotations, constructors, factories, or
local provenance; a variable merely named `session` is insufficient. Scalar
value APIs such as `session.scalar()` are not result objects.

```py
# Bad
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch(session: AsyncSession):
    return (await session.execute(statement)).scalars().all()

# Good
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch(session: AsyncSession):
    result = await session.execute(statement)
    return result.scalars().all()
```
