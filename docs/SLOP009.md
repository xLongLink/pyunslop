# SLOP009: Generators for SQL membership expressions

Pass a generator rather than a single-use list comprehension to SQLAlchemy
`.in_()`. Detection requires a recognized SQLAlchemy/SQLModel expression
constructor or a known query expression context. Existing list variables and
unrelated methods named `in_` are ignored.

```py
# Bad
from sqlalchemy import column

condition = column("user_id").in_([member.user_id for member in members])

# Good
from sqlalchemy import column

condition = column("user_id").in_(member.user_id for member in members)
```
