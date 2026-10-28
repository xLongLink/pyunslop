# SLOP022: Review borrowed-client-only classes

Review plain classes whose only state is a directly borrowed client and whose
methods only use that field. Owned clients, extra state, inheritance,
decorators, documented boundaries, properties, and lifecycle hooks are skipped.
Namespaced functions may be simpler, but preserve meaningful ownership or API
boundaries. The example assumes the class adds no intentional boundary.

```py
# Bad
class Users:
    def __init__(self, client):
        self.client = client

    def fetch(self):
        return self.client.fetch_users()

users = Users(client).fetch()

# Good
def fetch_users(client):
    return client.fetch_users()

users = fetch_users(client)
```
