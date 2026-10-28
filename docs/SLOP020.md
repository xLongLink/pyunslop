# SLOP020: Review size-only row loading

Review recognized query rows materialized solely for `len`, `bool`, or truth
testing, including local row variables whose only uses are size or truth checks.
Consider an existence or bounded query, but preserve locking, transaction
behavior, and threshold semantics. The checker does not rewrite SQL. The good
example assumes no row-locking or row-loading side effects are required.

```py
# Bad
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def has_users(session: AsyncSession):
    result = await session.execute(select(User))
    return bool(result.all())

# Good
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def has_users(session: AsyncSession):
    statement = select(select(User.id).exists())
    return bool(await session.scalar(statement))
```
