# Contributing Guidelines


Run it locally

```sh
uvx --from . pyunslop
```


## Architecture

```text
pyunslop/
    cli.py                  # CLI output and warning-only exit policy
    checker.py              # Public check_file orchestration
    discovery.py            # File discovery, exclusions, deduplication
    diagnostics.py          # Native Finding and public Warning records
    source.py               # Encoding-aware input, AST, shared tokens
    analysis/
        __init__.py         # Explicit AST-check pipeline
        bindings.py         # Position-sensitive Python name/scope handling
        queries.py          # SQLAlchemy/SQLModel checks and per-file state
        query_types.py      # Known database APIs and value classification
        endpoints.py        # FastAPI contracts and return summaries
        http.py             # HTTP and response recognition
    rules/
        comments.py         # Comment frequency, separation, spacing
        imports.py          # Retired wrappers and unittest policies
        module_doc.py       # Module documentation and CLI-help exemptions
        pytest.py           # Parametrization and collection safeguards
        pydantic.py         # Model field ordering
        simplifications.py  # Syntax-only review checks
        ...                 # Focused structural/comprehension helpers
    ruff.py                 # External Ruff lint/format integration
```


## Release


```bash
git fetch origin main
git tag vX.Y.Z origin/main
git push origin vX.Y.Z
```

