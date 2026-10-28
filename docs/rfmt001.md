# RFMT001: Match the fixed formatter preset

Source must match the bundled Ruff formatter preset: line length 140, Python
3.12 target, and `skip-magic-trailing-comma = true`. Project-local formatting
configuration does not override the preset. This check is read-only; formatting
differences are warnings and never automatically edit source or fail the CLI.

```example
# Bad
value=1

# Good
value = 1
```
