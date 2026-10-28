# SLOP015: Order model fields by name length

Within each blank-line-separated section of a directly recognized Pydantic
`BaseModel`, order annotated fields from shortest name to longest. Equal-length
names have no required order. Non-field statements, private attributes,
`model_config`, and recognized `ClassVar` annotations separate runs. Indirect
custom bases are not inferred. This is a style-policy warning, not an automatic
reorder: review validation dependencies, default factories, and serialization
order before changing fields. The example uses independent fields.

```py
# Bad
from pydantic import BaseModel

class UserResponse(BaseModel):
    description: str
    id: int

# Good
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    description: str
```
