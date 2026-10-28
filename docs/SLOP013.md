# SLOP013: No leading module docstrings

This fixed repository policy rejects leading module docstrings, not function
or class docstrings. A module is exempt when its `__doc__` explicitly supplies
`description`, `epilog`, or `help` to a recognized argparse, Click, or Typer API.
Simply referencing `__doc__` is not an exemption.

```py
# Bad
"""User lookup utilities."""

def find_user(user_id):
    return users.get(user_id)

# Good
def find_user(user_id):
    """Look up a user by identifier."""
    return users.get(user_id)
```
