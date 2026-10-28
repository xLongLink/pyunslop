# Agent workflow

- Install the package with `python -m pip install -e '.[test]'` in your environment.
- After Python changes, run `python -m pytest -v`.
- Run `pyunslop` from the project root and read the output even when it exits 0.
- Fix warnings in changed code and rerun the checker. Prefer simpler code and
  useful explanations over filler comments. Do not churn unrelated code to
  clear existing warnings.
- Keep checks warning-only: findings must not cause a nonzero CLI exit status.
- Review candidates are not proven safe fixes. Preserve intentional behavior,
  verify the documented safeguards, and explain warnings left in place.
