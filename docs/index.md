# PyChor

PyChor is a small Python library for writing choreographic programs. A
choreography describes the behavior of a distributed protocol from a global
point of view: which parties participate, which party owns each value, where
local computation happens, and when data is communicated between parties.

Writing a protocol this way keeps it in one readable piece. Instead of one
program per participant — where a send in one file has to be matched by hand
with a receive in another — a choreography states the exchange once, and every
party's behavior is derived from it. A protocol either lines up by construction
or fails to typecheck against the ownership rules; there is no third state where
two parties disagree about who speaks next.

The core API lives in `pychor.choreography` and is re-exported from `pychor`.
Most programs start by defining parties, entering a backend context, locating
values at parties, and composing local computations and sends.

```python
import pychor

alice = pychor.Party("alice")
bob = pychor.Party("bob")

with pychor.SimulationBackend(parties=[alice, bob]):
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    y = ((lambda value: value + 1) @ bob)(x.only(bob))
```

## Backends

The choreography above never names a transport, so the same protocol code runs
under any of the three bundled backends:

- **`SimulationBackend`** runs the whole choreography in one process, playing
  every party at once. It is the backend for design, teaching, and tests, and
  the only one that can draw a sequence diagram of the protocol.
- **`ForkingTCPBackend`** forks one local process per party and connects them
  over TCP. Use it to check that a protocol really is executable
  one-party-per-process, which `SimulationBackend` cannot tell you.
- **`TCPBackend`** is the deployment backend: one process per party, one party
  per machine, connected over a network.

See [Backends](backends.md) for how to choose between them and how to write your
own.

## What's here

- [Installation](installation.md) — installing PyChor, the optional extras, and
  what each backend needs from the platform.
- [Tutorial](tutorial.md) — a guided introduction, from a located constant to a
  protocol running across processes.
- [Concepts](concepts.md) — the execution model: ownership, where a computation
  runs, what every process knows, and how to read a party's view.
- [Backends](backends.md) — all three backends in detail, deployment, and the
  `ChoreographyBackend` interface.
- [Examples](examples.md) — the runnable protocols in `examples/`, from
  oblivious transfer to GMW circuit evaluation.
- [Testing](testing.md) — running the test suite, which is built out of those
  same examples.
- [API Reference](api.md) — generated reference for every public object.
