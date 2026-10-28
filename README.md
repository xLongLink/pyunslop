<div align="center">

<img src="banner.png" alt="pyunslop banner" />

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
| [SLOP003](docs/SLOP003.md) | Missing space after `#` (except a bare `#` or first-line shebang). |
| [SLOP004](docs/SLOP004.md) | Forbidden `noqa` suppression directive in a comment. |
| [SLOP005](docs/SLOP005.md) | Name asynchronous SQLAlchemy/SQLModel query results before consuming them. |
| [SLOP006](docs/SLOP006.md) | Use `Sequence[T]` for read-only query-result return types. |
| [SLOP007](docs/SLOP007.md) | Avoid redundant `list(result.all())` copies when a sequence is sufficient. |
| [SLOP008](docs/SLOP008.md) | Iterate buffered query results directly instead of iterating `result.all()`. |
| [SLOP009](docs/SLOP009.md) | Pass generators rather than single-use list comprehensions to SQLAlchemy `.in_()`. |
| [SLOP010](docs/SLOP010.md) | Name allowlisted domain-class instances before calling their methods. |
| [SLOP011](docs/SLOP011.md) | Declare FastAPI JSON endpoint response schemas explicitly. |
| [SLOP012](docs/SLOP012.md) | Return API payloads directly instead of generic success envelopes. |
| [SLOP013](docs/SLOP013.md) | Do not import retired `src.errors` wrappers. |
| [SLOP014](docs/SLOP014.md) | Reject leading module docstrings (CLI help exempt). |
| [SLOP015](docs/SLOP015.md) | Replace single literal-case pytest parametrization when it adds no fixture/collection behavior. |
| [SLOP016](docs/SLOP016.md) | Use pytest instead of unittest. |
| [SLOP017](docs/SLOP017.md) | Order Pydantic model fields from shortest name to longest within each section. |
| [SLOP018](docs/SLOP018.md) | Review response-model reconstruction when the route already declares that model. |
| [SLOP019](docs/SLOP019.md) | Use an explicit loop for dependent walrus bindings in comprehension constructor arguments. |
| [SLOP020](docs/SLOP020.md) | Review single-use list materialization for known iterable-only consumers. |
| [SLOP021](docs/SLOP021.md) | Prefer scalar query APIs for scalar-result consumption, preserving cardinality checks. |
| [SLOP022](docs/SLOP022.md) | Review rows loaded solely to check size, existence, or a threshold. |
| [SLOP023](docs/SLOP023.md) | Review transparent forwarding wrappers and subclasses with no added behavior. |
| [SLOP024](docs/SLOP024.md) | Review classes that only store and use a borrowed client. |
| [SLOP025](docs/SLOP025.md) | Review immediate post-commit ORM refreshes. |
| [SLOP026](docs/SLOP026.md) | Review inlining single-use literal constants. |

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
    "PGH003", "PT", "RUF100", "S324", "S506", "TID252",
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

[tool.ruff.lint.pep8-naming]
extend-ignore-names = ["visit_*"]
```

<br />

---

<div align="center">
LongLink 2026

[License](./LICENSE) &nbsp; - &nbsp; [Contributing](./CONTRIBUTING.md) &nbsp; - &nbsp; [Code of Conduct](./CODE_OF_CONDUCT.md) &nbsp; - &nbsp; [Contact](mailto:info@longlink.dev)

</div>

---
