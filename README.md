<div align="center">

<img src="banner.png" alt="pyunslop banner" />

<h3>Keep Python code clear, for humans and coding agents</h3>


[![Tests](https://github.com/xLongLink/pyunslop/actions/workflows/tests.yml/badge.svg)](https://github.com/xLongLink/pyunslop/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/pyunslop)](https://pypi.org/project/pyunslop/)
[![PyPI version](https://img.shields.io/pypi/v/pyunslop)](https://pypi.org/project/pyunslop/)

</div>

<br />

Run to flag the issues, ask you agent to fix them:

```
uvx pyunslop
```

<br />

## Rules

| Code | Warning |
| --- | --- |
| [CM001](docs/cm001.md) | More than 10 complexity points without a standalone comment. |
| [CM002](docs/cm002.md) | Missing blank line before a standalone comment block. |
| [CM003](docs/cm003.md) | Missing space after `#` (except a bare `#` or first-line shebang). |
| [CM004](docs/cm004.md) | Forbidden `noqa` suppression directive in a comment. |
| [PY001](docs/py001.md) | Name asynchronous SQLAlchemy/SQLModel query results before consuming them. |
| [PY002](docs/py002.md) | Use `Sequence[T]` for read-only query-result return types. |
| [PY003](docs/py003.md) | Avoid redundant `list(result.all())` copies when a sequence is sufficient. |
| [PY004](docs/py004.md) | Iterate buffered query results directly instead of iterating `result.all()`. |
| [PY005](docs/py005.md) | Pass generators rather than single-use list comprehensions to SQLAlchemy `.in_()`. |
| [PY006](docs/py006.md) | Name allowlisted domain-class instances before calling their methods. |
| [PY009](docs/py009.md) | Declare FastAPI JSON endpoint response schemas explicitly. |
| [PY010](docs/py010.md) | Return API payloads directly instead of generic success envelopes. |
| [PY013](docs/py013.md) | Do not import retired `src.errors` wrappers. |
| [PY014](docs/py014.md) | Reject leading module docstrings (CLI help exempt). |
| [PY015](docs/py015.md) | Replace single literal-case pytest parametrization when it adds no fixture/collection behavior. |
| [PY016](docs/py016.md) | Use pytest instead of unittest. |
| [PY017](docs/py017.md) | Order Pydantic model fields from shortest name to longest within each section. |
| [PY101](docs/py101.md) | Review response-model reconstruction when the route already declares that model. |
| [PY106](docs/py106.md) | Use an explicit loop for dependent walrus bindings in comprehension constructor arguments. |
| [PY107](docs/py107.md) | Review single-use list materialization for known iterable-only consumers. |
| [PY108](docs/py108.md) | Prefer scalar query APIs for scalar-result consumption, preserving cardinality checks. |
| [PY109](docs/py109.md) | Review rows loaded solely to check size, existence, or a threshold. |
| [PY110](docs/py110.md) | Review transparent forwarding wrappers and subclasses with no added behavior. |
| [PY111](docs/py111.md) | Review classes that only store and use a borrowed client. |
| [PY113](docs/py113.md) | Review immediate post-commit ORM refreshes. |
| [PY114](docs/py114.md) | Review inlining single-use literal constants. |

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
    "PGH003", "PT", "RUF100", "S324", "S506",
]
ignore = ["D100", "D104", "D202"]

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
