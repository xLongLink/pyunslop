# SLOP002: Separate comment blocks

Place a blank line before a standalone comment block. Only the first comment in
a block needs separation, including comments immediately after suite headers
such as `if` and `for`. File headings and comments inside continued bracketed
expressions are exempt.

```py
# Bad
users = fetch_users()
# Keep only active accounts.
active = [user for user in users if user.active]

# Good
users = fetch_users()

# Keep only active accounts.
active = [user for user in users if user.active]
```
