# Tutorial

## Choreographic Programming

In ordinary distributed programming, each participant is usually implemented as
a separate local program. In choreographic programming, you write a global
description of the protocol instead. The choreography says which parties exist,
where each value is located, which computations happen locally, and when values
are sent from one party to another.

PyChor represents participants with `Party` objects and values with
`LocatedVal` objects. A located value records the party or parties that can see
the value.

## Parties and Located Values

Create parties with `pychor.Party`:

```python
import pychor

alice = pychor.Party("alice")
bob = pychor.Party("bob")
```

PyChor operations run inside a backend. `LocalBackend` executes the choreography
in one Python process, which makes it useful for examples, testing, and protocol
design.

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    print(x)
```

The expression `5 @ alice` locates the value `5` at `alice`. It is shorthand for
`alice.constant(5)`.

## Local Computation

A local computation can run only where its located inputs are available. Use
`pychor.locally` to apply an ordinary Python function to located values:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    y = pychor.locally(lambda value: value + 1, x)
    print(y)
```

The result is located at the parties that could see the inputs.

You can also locate a function at a party with the `@` operator:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    increment_at_alice = (lambda value: value + 1) @ alice
    y = increment_at_alice(x)
```

For named reusable local functions, use `local_function`:

```python
@pychor.local_function
def add_bonus(value, bonus):
    return value + bonus

with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    y = add_bonus(x, 2)
```

Outside a backend context, a `local_function` behaves like the original Python
function. Inside a backend context, it produces a located result.

## Communication

Use `send` to communicate a located value from one party to another:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    x.send(src=alice, dest=bob)
```

After the send, `bob` can use the value in local computations. When a value is
available to multiple parties, `only` can narrow the ownership for the next
local computation:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    x.send(src=alice, dest=bob)

    y = ((lambda value: value + 1) @ bob)(x.only(bob))
    y.send(src=bob, dest=alice)

    result = pychor.locally(lambda value: value * 2, y.only(alice))
    print(result)
```

This choreography starts with a value at `alice`, sends it to `bob`, increments
it at `bob`, sends the result back to `alice`, and doubles it at `alice`.

## Structured Values

If a local computation returns a Python collection, PyChor can split the located
collection into located elements:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    pair = ((lambda value: (value, value + 1)) @ alice)(5 @ alice)
    first, second = pair.untup(2)
```

Use `unlist`, `untup`, and `undict` when a protocol needs to route individual
parts of a located collection to different parties.
