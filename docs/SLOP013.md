# SLOP013: No retired error wrappers

Do not import absolute `src.errors` wrappers, their submodules, or
`errors` through `from src import errors`. Use FastAPI's `HTTPException`
directly instead of recreating the retired exception-to-HTTP translation layer.
Relative and dynamic imports are not resolved. This is a fixed repository
policy, not a general rule against custom exception classes.

```py
# Bad
from src.errors import NotFoundError

def missing_user():
    raise NotFoundError("User not found")

# Good
from fastapi import HTTPException

def missing_user():
    raise HTTPException(status_code=404, detail="User not found")
```
