# SLOP020: Review single-use list materialization

Review simple list comprehensions consumed by built-in `sum`, `min`, `max`,
`tuple`, `set`, or `frozenset`, including adjacent single-use temporary lists
inside functions. Unknown consumers, short-circuiting `any`/`all`, visible
calls or awaits, asynchronous comprehensions, filters, and reused snapshots are
skipped. Properties may still have effects: preserve snapshot semantics and
exception timing. The example uses already available numeric values.

```py
# Bad
total = sum([value * 2 for value in values])

# Good
total = sum(value * 2 for value in values)
```
