# pyunslop

A Python code checker for humans and coding agents. Requires Python 3.10 or newer.
Ruff is installed automatically as a pinned dependency.

## Install

From this checkout:

```sh
python -m pip install .
```

Once published to PyPI:

```sh
python -m pip install pyunslop
```

## Use

```sh
pyunslop
```

Run it from your project directory. It scans all Python files recursively,
skipping common generated and virtual-environment directories. All rules are
always enabled, including PY013/PY014. The comment limit is fixed at 10 lines.
There are no command-line arguments, user configuration files, or rule toggles.

From this checkout with uv:

```sh
uv run pyunslop
# Or run in an isolated tool environment:
uvx --from . pyunslop
```

Once published to PyPI, `uvx pyunslop` will run it without a separate install.
`python -m pyunslop` is also supported after installation.

Rule definitions, examples, and safeguards are documented in the linked pages below.

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

Ruff entries without a numeric suffix select entire rule families; diagnostics
use individual codes such as `F401` or `S506`. `S324` and `S506` are explicitly
selected as well as belonging to `S`. The exclusions and conflict handling below
still apply; selecting a family does not override them.

## Ruff lint and formatting

Every `pyunslop` run also validates the supplied Ruff preset: line length 140,
Python 3.12 target, preview lint rules, and formatting with
`skip-magic-trailing-comma = true`. The exact configuration is in `pyproject.toml`
and bundled in the installed package's `ruff.toml`.

Ruff diagnostics retain their original rule codes (`F401`, `UP007`, `S506`, etc.)
and are reported as warnings. The table above describes each selected family
and individually selected rule.

`D100`, `D104`, and `D202` are ignored. Files under the scanned project's
`tests/` directory additionally ignore `ARG`, `N803`, and `S`. Import sorting uses
`no-sections = true`, `length-sort = true`, and `split-on-trailing-comma = false`.
Ruff resolves incompatible pydocstyle rules using its standard conflict handling.

The full `ANN` family is enabled, not just `ANN401`: missing parameter types,
missing return types, and dynamically typed `Any` annotations are reported as
warnings. These rules check annotations, not general type compatibility; they do
not replace a static type checker. The library ships a `py.typed` marker for
downstream type checking.

Both Ruff lint and format checks are read-only and use the same discovered Python
files as the native checks. Project-local Ruff settings cannot disable or change
this preset. No formatter, auto-fix, or cache writes are performed. Formatter
findings use `RFMT001` and do not make the command fail.

Suppression directives are not allowed: CM004 reports bare or code-specific
`# noqa` comments and file-wide `# ruff: noqa` / `# flake8: noqa` directives,
including case variants. Only actual comment tokens are inspected, so string
examples are ignored. Ruff lint runs with `--ignore-noqa`, so suppressed Ruff
findings remain visible. Native checks never honor suppressions either,
including directives targeting CM004 itself. Remove the directive and fix the
issue where appropriate; keep legitimate findings visible rather than
replacing suppressions with configuration exclusions or code workarounds.
The public `Warning` name and required AST visitor method names are retained
even when Ruff reports naming warnings. All findings remain advisory.

## Native comment checks and exit status

Function definitions and standalone comments reset the frequency counter. Blank
lines and inline comments do not. Multiline strings count at their start rather
than once per line; adjacent string literals count as one expression. Comment
blocks at suite starts and inside continued expressions need no preceding blank
line. These are source-line heuristics, not a measure of code or comment quality.

**All findings are warnings and exit with status 0**. Native checks skip unreadable
or invalid Python files; Ruff may report read/parse diagnostics as warnings.
Supplying arguments, encountering a directory traversal failure, or failing to run
Ruff exits with status 2. The checker never edits files
and does not use Python's `warnings` module, so `-W error` cannot promote findings
to exceptions.

## Coding agents

Add this instruction to your project's `AGENTS.md` (or equivalent):

```text
After changing Python files, run `pyunslop` from the project root.
Read the warnings even when the command exits successfully. Fix the warnings
in the changed code, then rerun the checker. Write useful comments explaining
intent or non-obvious behavior; do not add filler merely to satisfy CM001.
Prefer simplifying code when that removes the need for a comment.
Do not change unrelated files just to clear existing warnings.
For review candidates, verify the documented semantic safeguards before editing.
Preserve justified behavior and explain any warnings intentionally left in place.
```

Installing a package does not automatically make an agent run it. The project
instruction above tells the agent when to run the checker and act on its output.
No automatic rewriting, agent configuration changes, or hooks are installed.

## Library API

`check_file` runs the native rules and returns structured `Warning` objects with `path`, `line`, `column`,
`code`, and `message` fields. Locations are one-based. The same fixed settings
apply to the library API. File discovery raises `OSError` for missing paths or
traversal errors. Explicit library file paths are checked even inside excluded
directories, and overlapping discovery paths are deduplicated.
For the same batched Ruff checks used by the CLI, call
`pyunslop.ruff.check_ruff(paths)` with a list of discovered files, from
the project root. It returns the same warning objects; Ruff engine failures
raise `RuntimeError`.

Ruff does not expose a supported in-process Python linting API via `import ruff`.
`check_ruff` invokes the installed Ruff executable in a subprocess and parses its
JSON diagnostics. The executable is located through installed package metadata,
so a scanned project's `ruff.py` is never imported or executed. Both lint and
format checks are read-only; findings are returned as warnings rather than raised.

## Development

```sh
python -m pip install -e '.[test]'
python -m pytest -v
```

## Release

Configure a PyPI Trusted Publisher for `pyunslop` with this GitHub repository,
workflow filename `release.yml`, and environment name `pypi`. Create the matching
`pypi` environment in the repository's GitHub settings. No API token is needed.

Tag the desired commit on `main` and push the tag:

```bash
git fetch origin main
git tag vX.Y.Z origin/main
git push origin vX.Y.Z
```

The release workflow tests and builds the package, then publishes it to PyPI.
It verifies that the tagged commit belongs to the default branch and creates a
matching GitHub Release with generated notes only after publishing succeeds.
The PyPI version and GitHub Release therefore use the same tag and source commit.
The package version is taken from the tag (`v1.2.3` publishes version `1.2.3`);
the version in `pyproject.toml` does not need to be changed before tagging.

## Architecture

Native checks use Python's standard-library `ast` and `tokenize`; there is no
parser dependency or plugin registry. Each file is read, parsed, and tokenized
once, then analyzed by an explicit sequence of independent checks.

```text
src/pyunslop/
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

The binding visitor owns Python traversal mechanics, not framework knowledge
or findings. Import identities and inferred value categories are distinct
fields. Rebinding, parameter shadowing, branch merges, and nested scopes are
handled at their use sites rather than through a final module-wide alias map.

Query and endpoint analyzers own separate state and return findings; neither
receives the other's context. Simple rule helpers return findings instead of
mutating a shared engine. Several focused traversals are intentional: they
avoid callback-order dependencies without repeating source parsing. Tests for
internal analyzers use fixture helpers under `tests/`; the public API remains
`check_file`, `find_python_files`, and `Warning`.

All native findings use the same one-based location record before conversion
to public warnings. `checker.py` sorts native warnings by location and code;
`ruff.py` delegates Ruff rules to the pinned executable. The CLI remains
read-only, and findings never cause a nonzero exit status.
