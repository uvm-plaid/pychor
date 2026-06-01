# PyChor

PyChor is a small Python library for writing choreographic programs. A
choreography describes the behavior of a distributed protocol from a global
point of view: which parties participate, which party owns each value, where
local computation happens, and when data is communicated between parties.

The core API lives in `pychor.choreography` and is re-exported from `pychor`.
Most programs start by defining parties, entering a backend context, locating
values at parties, and composing local computations and sends.

```python
import pychor

alice = pychor.Party("alice")
bob = pychor.Party("bob")

with pychor.LocalBackend():
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    y = ((lambda value: value + 1) @ bob)(x.only(bob))
```

Use the [tutorial](tutorial.md) for a short introduction, or jump to the
[API reference](api.md) for the public choreography objects.
