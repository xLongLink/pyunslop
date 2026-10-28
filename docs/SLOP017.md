# SLOP017: Make comprehension argument dependencies explicit

Use an explicit loop when a walrus binding in one constructor argument is read
by a later argument inside a list, set, or dictionary comprehension or generator
expression. Constructors are recognized conservatively by capitalized names.
Independent bindings are unaffected. Preserve evaluation order and review
comprehension scope when moving bindings into a loop.

```py
# Bad
rows = [Row(value=(value := item.value), doubled=value * 2) for item in items]

# Good
rows = []
for item in items:
    value = item.value
    rows.append(Row(value=value, doubled=value * 2))
```
