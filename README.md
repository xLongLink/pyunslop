<div align="center">

<img src="https://raw.githubusercontent.com/xLongLink/pyunslop/main/banner.png" alt="pyunslop banner" />

<h3>Keep Python code clear, for humans and coding agents</h3>


[![Tests](https://github.com/xLongLink/pyunslop/actions/workflows/tests.yml/badge.svg)](https://github.com/xLongLink/pyunslop/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/pyunslop)](https://pypi.org/project/pyunslop/)

</div>

<br />

Run to flag the issues, ask you agent to fix them:

```
uvx pyunslop
```

Add to you `AGENTS.md` file:

```
DO run `uvx pyunslop` and fix any warnings
```


<br />

## Rules

| Code | Warning |
| --- | --- |
| [SLOP001](docs/SLOP001.md) | More than 10 complexity points without a standalone comment. |
| [SLOP002](docs/SLOP002.md) | Missing blank line before a standalone comment block. |
| [SLOP003](docs/SLOP003.md) | Forbidden `noqa` suppression directive in a comment. |
| [SLOP004](docs/SLOP004.md) | Name asynchronous SQLAlchemy/SQLModel query results before consuming them. |
| [SLOP005](docs/SLOP005.md) | Use `Sequence[T]` for read-only query-result return types. |
| [SLOP006](docs/SLOP006.md) | Avoid redundant `list(result.all())` copies when a sequence is sufficient. |
| [SLOP007](docs/SLOP007.md) | Iterate buffered query results directly instead of iterating `result.all()`. |
| [SLOP008](docs/SLOP008.md) | Pass generators rather than single-use list comprehensions to SQLAlchemy `.in_()`. |
| [SLOP009](docs/SLOP009.md) | Name allowlisted domain-class instances before calling their methods. |
| [SLOP010](docs/SLOP010.md) | Declare FastAPI JSON endpoint response schemas explicitly. |
| [SLOP011](docs/SLOP011.md) | Return API payloads directly instead of generic success envelopes. |
| [SLOP012](docs/SLOP012.md) | Reject leading module docstrings (CLI help and Alembic revision headers exempt). |
| [SLOP013](docs/SLOP013.md) | Replace single literal-case pytest parametrization when it adds no fixture/collection behavior. |
| [SLOP014](docs/SLOP014.md) | Order Pydantic model fields from shortest name to longest within each section. |
| [SLOP015](docs/SLOP015.md) | Review response-model reconstruction when the route already declares that model. |
| [SLOP016](docs/SLOP016.md) | Use an explicit loop for dependent walrus bindings in comprehension constructor arguments. |
| [SLOP017](docs/SLOP017.md) | Review single-use list materialization for known iterable-only consumers. |
| [SLOP018](docs/SLOP018.md) | Prefer scalar query APIs for scalar-result consumption, preserving cardinality checks. |
| [SLOP019](docs/SLOP019.md) | Review rows loaded solely to check size, existence, or a threshold. |
| [SLOP020](docs/SLOP020.md) | Review transparent forwarding wrappers and subclasses with no added behavior. |
| [SLOP021](docs/SLOP021.md) | Review classes that only store and use a borrowed client. |
| [SLOP022](docs/SLOP022.md) | Review immediate post-commit ORM refreshes. |
| [SLOP023](docs/SLOP023.md) | Review inlining single-use literal constants. |

<br />

## Suggested Ruff configurations

The rules complement an exising ruff configuration, this is our suggestion:

Install Ruff separately and add these settings to your `pyproject.toml`.
Run `ruff check` and `ruff format --check` separately; pyunslop does not run Ruff.

```toml
[tool.ruff]
line-length = 140
target-version = "py310"

[tool.ruff.format]
skip-magic-trailing-comma = true

[tool.ruff.lint]
preview = true
select = [
    "F", "UP", "D", "DTZ", "I", "ICN", "PIE", "RET", "ARG", "N",
    "PERF", "PTH", "A", "S", "ASYNC", "ANN", "B006", "E302", "E305",
    "E262", "E265", "C403", "C419",
    "PGH003", "PT", "RUF100", "TID252",
]
ignore = ["D100", "D104", "D202"]

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["ARG", "N803", "S"]

[tool.ruff.lint.isort]
no-sections = true
length-sort = true
split-on-trailing-comma = false
```

<br />

---

<div align="center">
LongLink 2026

[License](./LICENSE) &nbsp; - &nbsp; [Contributing](./CONTRIBUTING.md) &nbsp; - &nbsp; [Code of Conduct](./CODE_OF_CONDUCT.md) &nbsp; - &nbsp; [Contact](mailto:info@longlink.dev)

</div>

---
