# Tutorial

## Choreographic Programming

In ordinary distributed programming, each participant is usually implemented as
a separate local program. Keeping those programs consistent is the hard part: a
send in one file has to be matched by hand with a receive in another, and
nothing checks that the two agree. Most protocol bugs live in that gap.

In choreographic programming, you write a global description of the protocol
instead. The choreography says which parties exist, where each value is
located, which computations happen locally, and when values are sent from one
party to another. Each participant's behavior is then derived from that single
description, so the sends and receives cannot drift apart.

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
    print(x)                # 5@{alice}
```

The expression `5 @ alice` locates the value `5` at `alice`. It is shorthand for
`alice.constant(5)`.

Printing a located value shows both halves of it: the underlying value and the
set of parties that can see it. Watching that set change is the easiest way to
follow what a choreography is doing.

## Local Computation

A local computation can run only where its located inputs are available. Use
`pychor.locally` to apply an ordinary Python function to located values:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    y = pychor.locally(lambda value: value + 1, x)
    print(y)                # 6@{alice}
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
function. Inside a backend context, it produces a located result. That makes it
convenient to unit-test protocol helpers on plain values without a backend.

## Arithmetic on Located Values

Located values support `+`, `-`, `*`, `/`, `%`, and unary `-` directly. Each
operator is shorthand for a local computation, so `x + y` runs wherever both
operands are available and yields a new located value:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    y = 6 @ alice
    print(x + y)            # 11@{alice}
    print(x * 2)            # 10@{alice}
```

Plain Python numbers may appear on either side, and place no constraint on
where the computation runs.

This is what keeps real protocols readable. In `examples/protocol_beaver.py`, a
Beaver-triple multiplication — several rounds of communication over secret
shares — computes its result like this:

```python
d = d1 + d2
e = e1 + e2
r_1 = d * e + d * b1 + e * a1 + c1
r_2 = d * b2 + e * a2 + c2
```

Every operation there is a local computation at whichever party owns the
operands, and PyChor works out which party that is.

## Communication

Use `send` to communicate a located value from one party to another:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    print(x)                # 5@{alice, bob}
```

Note that `send` modifies `x` in place rather than returning a new value: after
the send, `x` is owned by *both* parties, and either can use it.

That is exactly why `only` is often needed next. A local computation runs at
every party that owns its inputs, so a computation over `x` would now run at
both parties. `only` narrows ownership to say whose value you mean:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    x = 5 @ alice
    x.send(src=alice, dest=bob)

    y = ((lambda value: value + 1) @ bob)(x.only(bob))
    y.send(src=bob, dest=alice)

    result = pychor.locally(lambda value: value * 2, y.only(alice))
    print(result)           # 12@{alice}
```

This choreography starts with a value at `alice`, sends it to `bob`, increments
it at `bob`, sends the result back to `alice`, and doubles it at `alice`.

Sends can carry a label, which is useful when the payload itself is unreadable —
a hash, a ciphertext, or a share:

```python
hash_val.send(sender, receiver, note='hash of committed value')
```

`LocalBackend` puts that label on the corresponding edge of the sequence
diagram it records for the protocol; see
[Sequence diagrams](concepts.md#sequence-diagrams).

## Structured Values

If a local computation returns a Python collection, PyChor can split the located
collection into located elements:

```python
with pychor.LocalBackend(parties=[alice, bob]):
    pair = ((lambda value: (value, value + 1)) @ alice)(5 @ alice)
    first, second = pair.untup(2)
```

Use `unlist`, `untup`, and `undict` when a protocol needs to route individual
parts of a located collection to different parties. This is how secret sharing
is written: one local computation generates all the shares, and then each share
is sent to its own party.

```python
@pychor.local_function
def share(x):
    s1 = GF.Random()
    s2 = GF(x) - s1
    return s1, s2

s1, s2 = share(secret).untup(2)
s2.send(alice, bob)
```

## Running It for Real

Everything above ran in one process. The same choreography runs across
processes, and the only line that changes is the `with`:

```python
with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=10100):
    x = 5 @ alice
    x.send(src=alice, dest=bob)

    y = ((lambda value: value + 1) @ bob)(x.only(bob))
    y.send(src=bob, dest=alice)

    result = pychor.locally(lambda value: value * 2, y.only(alice))
    print(result)
```

`ForkingTCPBackend` forks one process per party and connects them over TCP, so
each party genuinely holds only its own data. Running a protocol this way is
worth doing even during development, because `LocalBackend` cannot detect a
choreography that reads a value it does not own — in one process, the value is
always there.

You will notice two differences. The body now runs once per party, so the
`print` above appears once per process. And in the processes where a value is
not owned, it holds `None` rather than the real thing — which is the rule that
matters most when writing a protocol you intend to deploy.

Read [Concepts](concepts.md) next for that rule and the reasoning behind it, or
[Backends](backends.md) for deploying a choreography across machines.
