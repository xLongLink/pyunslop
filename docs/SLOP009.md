# SLOP009: Name instances and use multiline construction

Assign class instances to names before calling their methods, including methods
reached through attributes. Constructor assignments with arguments must span
multiple lines. Zero-argument assignments such as `client = Client()` are exempt
from formatting requirements, but `Client().fetch()` still requires an assignment.

```py
class Client:
    pass

# Bad
result = Client(config).applications.fetch()
client = Client(config)

# Good
client = Client(
    config,
)
result = client.applications.fetch()
```

## Constructor resolution

The rule uses class definitions, not a class-name allowlist or capitalization:

- Undecorated classes declared in the inspected file, assignment aliases to those
  classes, and directly declared nested classes are recognized.
- When scanning a file on disk, directly declared classes in adjacent Python
  modules or the containing package root are recognized through `from` imports
  (including relative imports and aliases) and module-qualified access such as
  `import services as svc; svc.Client(config).fetch()`.
- Imported modules are parsed, never imported or executed. Installed dependencies,
  re-exports, dynamic exports, decorated classes, and unresolved constructor
  identities are excluded. Rebound or ambiguous exported classes are excluded.
- Parameters and assignments that shadow known classes clear their identities.

Ordinary functions and unresolved factory calls, including intentional fluent
factory APIs such as `builder(config).configure().build()`, are not checked.
Known class constructors are checked even when used as fluent entry points;
method return values and subsequent fluent calls are not inferred as constructors.
The multiline check applies to direct assignments to names, including annotated
assignments. It does not prescribe formatting for other constructor expressions.
