# SLOP024: Review single-use literal constants

Review uppercase function-local and private module constants assigned an
immutable literal and read exactly once later in the same scope. Rebinding,
nested-scope or comprehension references, annotations, mutable or computed
values, class constants, public module names, explicit exports, and recognized
dynamic namespace access are skipped. Preserve names that explain units,
domain meaning, or boundaries. A warning does not prove that inlining improves
readability or preserves identity; the example assumes the name adds no meaning.

```py
# Bad
def render():
    LABEL = "Ready"
    return format_label(LABEL)

# Good
def render():
    return format_label("Ready")
```
