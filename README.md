# pyunslop

A Python code checker for humans and coding agents. Requires Python 3.10 or newer.
Ruff is installed automatically as a pinned dependency.

```
uvx pyunslop
```

From this checkout with uv:


## Rules

| Code | Warning |
| --- | --- |
| [CM001](docs/cm001.md) | More than 10 non-import code lines without a standalone comment. |
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
| [RFMT001](docs/rfmt001.md) | Source does not match the fixed Ruff formatter preset. |
| [F](https://docs.astral.sh/ruff/rules/#pyflakes-f) | Pyflakes: unused imports, undefined names, and other correctness checks. |
| [UP](https://docs.astral.sh/ruff/rules/#pyupgrade-up) | pyupgrade: modern Python syntax and APIs. |
| [D](https://docs.astral.sh/ruff/rules/#pydocstyle-d) | pydocstyle: docstring presence and conventions. |
| [DTZ](https://docs.astral.sh/ruff/rules/#flake8-datetimez-dtz) | flake8-datetimez: timezone-aware datetime usage. |
| [I](https://docs.astral.sh/ruff/rules/#isort-i) | isort: import sorting and formatting. |
| [ICN](https://docs.astral.sh/ruff/rules/#flake8-import-conventions-icn) | flake8-import-conventions: conventional import aliases. |
| [PIE](https://docs.astral.sh/ruff/rules/#flake8-pie-pie) | flake8-pie: unnecessary or redundant code. |
| [RET](https://docs.astral.sh/ruff/rules/#flake8-return-ret) | flake8-return: return-statement consistency and simplification. |
| [ARG](https://docs.astral.sh/ruff/rules/#flake8-unused-arguments-arg) | flake8-unused-arguments: unused function and method arguments. |
| [N](https://docs.astral.sh/ruff/rules/#pep8-naming-n) | pep8-naming: Python naming conventions. |
| [PERF](https://docs.astral.sh/ruff/rules/#perflint-perf) | Perflint: common performance pitfalls. |
| [PTH](https://docs.astral.sh/ruff/rules/#flake8-use-pathlib-pth) | flake8-use-pathlib: prefer pathlib APIs. |
| [A](https://docs.astral.sh/ruff/rules/#flake8-builtins-a) | flake8-builtins: names shadowing Python builtins. |
| [S](https://docs.astral.sh/ruff/rules/#flake8-bandit-s) | flake8-bandit: potential security issues. |
| [ASYNC](https://docs.astral.sh/ruff/rules/#flake8-async-async) | flake8-async: asynchronous code pitfalls. |
| [ANN](https://docs.astral.sh/ruff/rules/#flake8-annotations-ann) | Require argument and return annotations, including avoiding explicit `Any` (ANN401). |
| [B006](https://docs.astral.sh/ruff/rules/mutable-argument-default/) | Avoid mutable default argument values. |
| [E302](https://docs.astral.sh/ruff/rules/blank-lines-top-level/) | Require the expected blank lines before definitions. |
| [E305](https://docs.astral.sh/ruff/rules/blank-lines-after-function-or-class/) | Require the expected blank lines after definitions. |
| [PGH003](https://docs.astral.sh/ruff/rules/blanket-type-ignore/) | Require specific codes in type-ignore comments. |
| [PT](https://docs.astral.sh/ruff/rules/#flake8-pytest-style-pt) | flake8-pytest-style: pytest conventions and test simplification. |
| [RUF100](https://docs.astral.sh/ruff/rules/unused-noqa/) | Remove unused `noqa` directives. |
| [S324](https://docs.astral.sh/ruff/rules/hashlib-insecure-hash-function/) | Review insecure hash functions. |
| [S506](https://docs.astral.sh/ruff/rules/unsafe-yaml-load/) | Avoid unsafe YAML loading. |


