# SLOP003: No suppression directives

Do not use bare or code-specific `noqa` directives, including file-wide
`ruff: noqa` and `flake8: noqa` forms and case variants. Detection uses real
comment tokens, not string contents. These directives cannot suppress pyunslop
findings. Fix the issue where appropriate; keep legitimate warnings visible rather than adding
another bypass. Findings remain warning-only.

```py
# Bad
import os  # noqa: F401
value = 1

# Good
value = 1
```
