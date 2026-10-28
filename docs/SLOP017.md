# SLOP017: Review single-use list materialization

Review simple list comprehensions passed directly to built-in `tuple` or
`frozenset`, and adjacent single-use temporary lists consumed by `sum`, `min`,
`max`, `tuple`, `set`, or `frozenset` inside functions. Direct `sum`, `min`,
`max`, and `set` calls are delegated to Ruff C419/C403; enable preview for
C419's `sum`/`min`/`max` coverage. Unknown consumers, short-circuiting `any`/`all`, visible
calls or awaits, asynchronous comprehensions, filters, and reused snapshots are
skipped. Properties may still have effects: preserve snapshot semantics and
exception timing. The example uses already available numeric values.

```py
# Bad
total = tuple([value * 2 for value in values])

# Good
total = tuple(value * 2 for value in values)
```
