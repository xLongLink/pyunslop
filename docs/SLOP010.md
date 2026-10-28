# SLOP010: Name domain instances

Assign `Postgres` and `Kubernetes` instances before calling their methods,
including methods reached through attributes. Imported aliases and
module-qualified constructors are recognized. This explicit class-name
allowlist does not apply to other classes or ordinary fluent APIs.

```py
# Bad
from services import Postgres

async def inspect_database(config):
    return await Postgres(config).usage()

# Good
from services import Postgres

async def inspect_database(config):
    database = Postgres(config)
    return await database.usage()
```
