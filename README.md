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

```text
example.py:12:1: warning: CM001 more than 10 code lines without a standalone comment
```

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

The enforced lint selection is:

```toml
[tool.ruff.lint]
preview = true
select = ["F", "UP", "D", "DTZ", "I", "ICN", "PIE", "RET", "ARG", "N", "PERF", "PTH", "A", "S", "ASYNC", "ANN", "B006", "E302", "E305", "PGH003", "PT", "RUF100", "S324", "S506"]
ignore = ["D100", "D104", "D202"]
```

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

## Query-result checks

These rules use imports, session/result annotations, session constructors and
factories, and local result assignments to recognize SQLAlchemy/SQLModel APIs.
Import aliases and quoted annotations are supported. SQLAlchemy and SQLModel
do not need to be installed to check source files. An untyped variable merely
named `session` or `result` is not enough to trigger a warning.

**PY001:** assign the awaited result before chaining result methods:

```python
# Bad
rows = (await session.execute(statement)).scalars().all()

# Good
result = await session.execute(statement)
rows = result.scalars().all()
```

Recognized query methods include `execute`, `scalars`, `stream`, `stream_scalars`,
and SQLModel's `exec`. Scalar-value queries such as `session.scalar(...)` are not
treated as result objects.

**PY002:** when a function directly returns query rows, do not declare `list[T]`
just to wrap those rows in `list()`:

```python
from collections.abc import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

async def fetch_users(session: AsyncSession) -> Sequence[User]:
    result = await session.scalars(select(User))
    return result.all()
```

The rule flags `list[T]` and `typing.List[T]` contracts on direct query-row
returns, including `return list(result.all())`. It does not flag ordinary
functions that build and return mutable lists.

**PY003:** prefer `users = result.all()` to `users = list(result.all())`.
Also applies to `fetchall()` and result transformations such as `scalars()` or
`unique()`. The rule checks untyped local assignments, `Sequence`-annotated
assignments, and returns annotated as `Sequence`. Explicit mutable-list
contracts and calls to unknown consumers are left alone.

**PY004:** prefer `for user in result:` to `for user in result.all():`.
Only direct synchronous `for` loops over recognized buffered/synchronous query
results are checked. Streaming APIs (`stream`, `stream_scalars`), `AsyncResult`
types, `yield_per`, unknown result objects, and materialized lists used elsewhere
are left alone.

**PY005:** prefer `col(User.id).in_(member.user_id for member in members)` to
`col(User.id).in_([member.user_id for member in members])`. Detection requires a
recognized SQLAlchemy/SQLModel expression constructor (`column`, `col`, etc.) or
a known `select(...).where(...)`, `filter(...)`, or `having(...)` expression
context. Existing list variables and unrelated methods named `in_` are ignored.

These are local static heuristics, not a full type checker: they do not infer
session types across files or prove that an untyped variable is never mutated.
Review warnings before removing a copy that intentionally provides mutability.

## Named domain instances

**PY006:** assign domain instances before calling methods on them:

```python
database = Postgres(host, port, username, password, sslmode)
usage = await database.usage()

cluster = Kubernetes(config)
logs = await cluster.applications.logs(name)
```

The explicit class-name allowlist is `Postgres` and `Kubernetes`. Imported aliases
and module-qualified constructors are recognized. Other classes and ordinary
fluent APIs are not subject to this rule.

## FastAPI checks

These checks recognize locally constructed or annotated `FastAPI`/`APIRouter`
objects, including import aliases. They do not infer imported router instances
across files. Both synchronous and asynchronous HTTP endpoints are checked.

**PY009:** declare schemas explicitly, even when a function has a return annotation:

```python
@router.get('/users', response_model=list[UserResponse])
async def list_users():
    return await users.fetch()
```

Exemptions include HEAD routes, bodyless statuses (1xx, 204, 205, 304), explicit
streaming/redirect/raw response classes, raw-response annotations, and functions
whose explicit returns are all recognized raw response objects. WebSocket
handlers are not checked. `response_model=None` is an explicit schema opt-out;
unknown `**route_options` are skipped rather than guessed. Merely setting
`response_class=JSONResponse` does not exempt a normal JSON endpoint.

**PY010:** return the payload, not
`{'success': True, 'detail': 'Users fetched', 'data': users}`. Direct dictionary
returns, `dict(...)` constructors, and locally assigned envelopes are recognized.
The warning requires literal `success=True` plus `detail` or `data`. Non-route
functions and ordinary payload dictionaries are not flagged.

External protocol contracts can explicitly opt out without dropping their schema:

```python
@router.post(
    '/external-protocol',
    response_model=ProtocolResponse,
    openapi_extra={'x-external-protocol': True},
)
async def protocol_endpoint():
    return {'success': True, 'detail': 'OK', 'data': payload}
```

`response_model=None` alone does **not** exempt success envelopes from PY010.
All these rules remain warnings; no framework needs to be installed for scanning.

## Repository-specific policies

PY013 and PY014 are **always enabled**. These are deliberately fixed policies
adopted by this tool, not claims about general Python best practices.

- **PY013:** warns on absolute `src.errors` imports, its submodules, and
  `from src import errors`. Use FastAPI's `HTTPException` directly instead of
  recreating the retired exception-to-HTTP translation layer. Relative and
  dynamic imports are not resolved.
- **PY014:** detects only leading module docstrings via `ast.get_docstring`.
  Function/class docstrings are unaffected. A module is exempt when its
  `__doc__` is used explicitly for help in a recognized argparse, Click, or
  Typer constructor/decorator (`description`, `epilog`, or `help`).

## Test framework and parametrization rules

**PY016** flags absolute `unittest` imports, including aliases, `from` imports,
and submodules such as `unittest.mock`. Use pytest-style tests, plain assertions,
fixtures, and `pytest.raises` instead. For mocking, consider pytest's `monkeypatch`
fixture or the pytest-mock plugin. Relative and dynamic imports are not resolved.
This is a fixed policy, not an automatic migration: existing tests are never rewritten.

**PY017** checks annotated fields in classes directly inheriting from imported
Pydantic `BaseModel` (including aliases and module-qualified imports). Within
each blank-line-separated section, field names should run from shortest to
longest; equal-length names have no required order. Non-field statements,
private attributes, `model_config`, and recognized `ClassVar` annotations also
separate field runs. Indirect or imported custom model bases are not inferred.
This is a repository style policy, not a general Python requirement. Findings
are warnings only: review validation dependencies, default factories, and any
intentional serialization order before manually reordering. No fields are
automatically moved.

**PY015** flags exactly one literal case in a known `pytest.mark.parametrize`
decorator. Dynamic cases, `pytest.param(...)`, explicit IDs or scopes, indirect
fixtures, tests using `request`, and modules with known collection hooks are
left alone. Ordinary multi-case tests are unaffected.

The following rules identify **review candidates**, not proven safe edits.
They have the same warning-only exit behavior as every other rule. Do not
mechanically apply their suggestions.

- **PY101:** flags a direct `return Model.model_validate(value)` when all known
  route response-model contracts match `Model`. Explicit validation options,
  computed/transformed inputs, external protocols, and locally visible model
  validators or custom initialization are exempt. Imported model validators
  cannot be inspected; preserve intentional transformations.
- **PY106:** detects a walrus binding in one constructor argument reused by a
  later argument inside a list/set/dict comprehension or generator expression.
  Constructors are recognized conservatively by capitalized names. An explicit
  loop makes evaluation dependencies clear.
- **PY107:** checks simple list comprehensions passed directly to built-in
  `sum`, `min`, `max`, `tuple`, `set`, or `frozenset`, and adjacent single-use
  temporary lists in functions. Unknown consumers, short-circuiting `any`/`all`,
  effectful calls/awaits, async comprehensions, filters, and reused snapshots are
  skipped. Attribute/property access can still have effects: verify snapshot
  semantics and exception timing before switching to a generator.
- **PY108:** identifies known `execute(...).scalars()` result consumption and
  single-element row unpacking from syntactically single-selection queries.
  Prefer `session.scalars(statement)`, but retain the existing `one`,
  `one_or_none`, or other cardinality/null-handling behavior. Multi-column
  unpacking and unknown query shapes are not rewritten or simplified.
- **PY109:** flags known query rows materialized directly for `len`, `bool`, or
  truth testing, plus local row variables whose only uses are size/truth checks.
  Review an existence or bounded query while preserving locking, transaction
  behavior, and threshold semantics. It does not rewrite SQL.
- **PY110:** reviews exact private positional forwarding functions and private
  empty subclasses, plus the known empty FastAPI/Starlette test-client subclass
  pattern. Public functions, typed/documented/decorated contracts, inherited
  framework methods, and subclasses adding behavior are exempt. Preserve any
  meaningful compatibility or lifecycle boundary.
- **PY111:** reviews plain classes with only a directly borrowed client field
  and instance methods using it. Owned clients, extra state, inheritance,
  decorators, documented boundaries, properties, and lifecycle hooks are skipped.
  Namespaced functions may be simpler; the checker never removes a class.
- **PY113:** flags an immediate commit/refresh pair on the same known session.
  It does **not** prove the refresh redundant. Before removing it, check
  `expire_on_commit`, server-generated defaults, and required relationships.
- **PY114:** reviews uppercase function-local and private module constants assigned
  an immutable literal and read exactly once later in the same scope. For example,
  consider replacing `TIMEOUT = 30; connect(timeout=TIMEOUT)` with
  `connect(timeout=30)`. Rebinding, nested-scope/comprehension references, annotated
  assignments, mutable or computed values, class constants, public module names,
  explicit module exports, and recognized dynamic namespace access are skipped.
  Preserve names that explain units, domain meaning, or intentional boundaries;
  this warning is not proof that inlining improves readability or preserves identity.

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

```python
from pathlib import Path
from pyunslop import check_file, find_python_files

for path in find_python_files([Path("src")]):
    for warning in check_file(path):
        print(warning)
```

`check_file` runs the native rules and returns structured `Warning` objects with `path`, `line`, `column`,
`code`, and `message` fields. Locations are one-based. The same fixed settings
apply to the library API. File discovery raises `OSError` for missing paths or
traversal errors. Explicit library file paths are checked even inside excluded
directories, and overlapping discovery paths are deduplicated.
For the same batched Ruff checks used by the CLI, call
`pyunslop.ruff.check_ruff(paths)` with a list of discovered files, from
the project root. It returns the same warning objects; Ruff engine failures
raise `RuntimeError`.

```python
from pathlib import Path
from pyunslop import find_python_files
from pyunslop.ruff import check_ruff

for warning in check_ruff(list(find_python_files([Path(".")]))):
    print(warning)
```

Ruff does not expose a supported in-process Python linting API via `import ruff`.
`check_ruff` invokes the installed Ruff executable in a subprocess and parses its
JSON diagnostics. The executable is located through installed package metadata,
so a scanned project's `ruff.py` is never imported or executed. Both lint and
format checks are read-only; findings are returned as warnings rather than raised.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
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
