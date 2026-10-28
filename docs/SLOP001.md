# SLOP001: Uncommented complexity budget

Warn when an uncommented run exceeds a fixed budget of 10 points:

- Ordinary non-import code lines cost 1 point.
- Function signatures count once, regardless of how many lines their parameters
  and annotations occupy. Their bodies still count normally.
- Literal-only lists, tuples, sets, and dictionaries count once, including nested
  containers and signed numbers. Item lines and closing delimiters do not add
  points; executable code following a closing delimiter still counts.
- Control-flow headers (`if`, `for`, `while`, `try`, `except`, `with`, `match`,
  and `case`, including asynchronous and `except*` variants) cost 2 points,
  plus 1 per enclosing control-flow level. `elif` is a nested `if`.
- Ordinary statements inside nested blocks still cost only 1 point per line.
  Multiple headers on one physical line use the largest weight. Continuation
  lines in nonliteral expressions retain their ordinary 1-point cost.

Function definitions and standalone comments reset the budget; blank lines and
inline comments do not. Function bodies start with no inherited control-flow
nesting. Imports do not count. Multiline and adjacent strings count at their
expression start. Calls, comprehensions, unpacking, and computed collection
values are not literal-only containers.

Report only the first line crossing the budget until the next reset. This is a
readability heuristic, not cyclomatic complexity. Prefer simpler code or a useful
explanation, not filler comments. Findings remain warning-only.

```py
# Bad
total = 0
total += january
total += february
total += march
total += april
total += may
total += june
total += july
total += august
total += september
total += october

# Good
total = sum(monthly_totals)
```
