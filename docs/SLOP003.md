# SLOP003: Space after comment markers

Start comments with `# ` rather than attaching text directly to `#`. A bare `#`
and a first-line shebang are exempt. Hash characters inside strings are not
comments.

```py
# Bad
#Fetch active accounts.
users = fetch_users()

# Good
# Fetch active accounts.
users = fetch_users()
```
