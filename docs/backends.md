# Backends

A choreography says *what* a protocol does; a backend decides *how* it runs. The
choreography itself never names a backend, so the same protocol code runs
unchanged in a single process, across forked local processes, or across
machines — you choose by picking which context manager to enter.

## Choosing a backend

| | `LocalBackend` | `ForkingTCPBackend` | `TCPBackend` |
| --- | --- | --- | --- |
| Processes | 1, playing every party | one per party, forked | one per party, launched by you |
| Real network | no | loopback TCP | yes |
| Platform | anywhere | Unix (needs `os.fork`) | anywhere |
| Sequence diagram | yes | no | no |
| All parties' views readable | yes | no, only the local party's | no, only the local party's |
| Catches illegal reads | no | yes | yes |
| Use it for | design, teaching, tests, security experiments | checking a protocol is genuinely distributable | deployment |

The progression is the intended workflow. Design a protocol under
`LocalBackend`, where you can print a sequence diagram and inspect every
party's view at once. Then run it under `ForkingTCPBackend` to prove it really
executes one-party-per-process — `LocalBackend` cannot catch a choreography that
reads a value it does not own, because in one process the value is always there.
Deploy with `TCPBackend`.

## Writing backend-agnostic choreographies

Take the backend as a parameter rather than hard-coding it, and a protocol
becomes runnable under all three:

```python
def sum_protocol(backend, parties):
    with backend(parties=parties) as b:
        ...
```

The bundled examples do this by selecting the backend from the environment.
`examples/example_backend.py` is the whole mechanism:

```python
import os
import pychor

def backend(parties):
    backend_name = os.environ.get('PYCHOR_BACKEND', 'local').lower()

    if backend_name == 'local':
        return pychor.LocalBackend(parties=parties)
    if backend_name == 'forking_tcp':
        base_port = int(os.environ.get('PYCHOR_TCP_BASE_PORT', '10000'))
        return pychor.ForkingTCPBackend(parties=parties, base_port=base_port)
    if backend_name == 'tcp':
        return _tcp_backend(parties)

    raise ValueError(...)
```

Every example then writes `from example_backend import backend` and
`with backend(parties=[...])`, so `examples/run_tests.py` can run the whole
suite under two different backends without editing a line of protocol code.

The variables it reads:

| Variable | Meaning |
| --- | --- |
| `PYCHOR_BACKEND` | `local` (default), `forking_tcp`, or `tcp`. |
| `PYCHOR_TCP_BASE_PORT` | For `forking_tcp`: port of the first party. Default `10000`. |
| `PYCHOR_TCP_ME` | For `tcp`: the name of the party this process plays. Required. |
| `PYCHOR_TCP_ADDRESSES` | For `tcp`: `party=host:port` entries separated by commas, covering every party. Required. |
| `PYCHOR_TCP_CONNECT_TIMEOUT` | Seconds to wait for the party mesh. Default `10.0`. |

## `LocalBackend`

`LocalBackend` runs the entire choreography in the calling process, playing
every party itself.

```python
with pychor.LocalBackend(parties=[alice, bob]) as backend:
    x = 5 @ alice
    x.send(src=alice, dest=bob)

    print(backend.views[bob])          # [5]
    backend.print_sequence_diagram()
```

Because one process holds everything, this backend can observe the protocol as a
whole. Two capabilities follow from that, and neither is available from the TCP
backends:

- **Sequence diagrams.** Every send is recorded as Mermaid source in `uml`. See
  [Sequence diagrams](concepts.md#sequence-diagrams).
- **All parties' views.** `backend.views` is populated for every party, which is
  what makes executable security experiments possible. See
  [Views and security proofs](concepts.md#views-and-security-proofs).

The cost of that convenience is fidelity: nothing is actually distributed, so a
choreography that reads a value belonging to someone else still finds a real
value in memory and runs happily. Treat a passing `LocalBackend` run as evidence
that the protocol computes the right answer, not that it is executable.

## `ForkingTCPBackend`

`ForkingTCPBackend` is the bridge between design and deployment. It forks one
process per party on the local machine and connects them with `TCPBackend`, so
you get real one-party-per-process execution with no setup:

```python
with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=10100):
    x = 5 @ alice
    x.send(src=alice, dest=bob)
```

Ports are assigned by position in `parties`: the first party listens on
`base_port`, the second on `base_port + 1`, and so on. Concurrent runs therefore
need non-overlapping windows — `examples/run_tests.py` gives each test file its
own range with `PYCHOR_TCP_BASE_PORT = 10000 + test_index * 100`.

Three behaviors are worth knowing before you use it:

- **The body runs once per party, in different processes.** Output from the
  parties interleaves, and a side effect such as writing a file happens once per
  party. Anything you want to happen exactly once must be guarded by the party
  it belongs to.
- **`__enter__` returns the inner `TCPBackend`.** In
  `with pychor.ForkingTCPBackend(...) as b`, `b` is a `TCPBackend` for *this*
  process's party, so `b.views` holds only that party's messages.
- **Child failures surface in the parent.** The parent process plays
  `parties[0]`, waits for every child on exit, and raises `RuntimeError` if any
  exited non-zero; the child's traceback appears on stderr as usual. This is
  what lets `run_tests.py` treat a zero exit status as a pass.

It requires `os.fork`, so it does not run on Windows.

## `TCPBackend`

`TCPBackend` is the deployment backend. It does not fork: you launch one process
per party, each of which constructs the backend with its own party as `me` and
an address map covering everyone.

```python
import sys
import pychor

alice = pychor.Party('alice')
bob = pychor.Party('bob')

PARTIES = [alice, bob]
ADDRESSES = {
    alice: ('10.0.0.1', 10000),
    bob:   ('10.0.0.2', 10000),
}

me = {p.name: p for p in PARTIES}[sys.argv[1]]

with pychor.TCPBackend(parties=PARTIES, me=me, addresses=ADDRESSES):
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    y = ((lambda v: v + 1) @ bob)(x.only(bob))
    y.send(src=bob, dest=alice)
```

Run the *same file* on each host:

=== "On 10.0.0.1"

    ```bash
    python protocol.py alice
    ```

=== "On 10.0.0.2"

    ```bash
    python protocol.py bob
    ```

Three requirements come with this backend:

**Every process must agree on `parties` and on its order.** The order breaks the
symmetry of connection setup: each party binds its own address and accepts one
connection from every *lower*-indexed party, then dials every *higher*-indexed
party, sending its index as a handshake. If two processes disagree about the
order, they will both dial or both listen and never connect.

**Processes may start in any order, but all within `connect_timeout`.** Entering
the context blocks until the full mesh is up. Dialing retries every 50 ms, so a
party that starts first simply waits. If the mesh is not complete within
`connect_timeout` seconds (default 10), setup raises `TimeoutError` naming the
party it was waiting for. Raise it for a staggered rollout.

**`addresses` must cover exactly the party set.** A missing or unknown party
raises `ValueError` at construction, and a malformed entry raises `TypeError` —
before any socket is opened. Each party binds its own entry, so those hosts must
be bindable locally and reachable remotely, with the ports open.

### Security

Both TCP backends move values as pickled Python objects, and unpickling
executes arbitrary code chosen by the sender. There is no authentication and no
encryption: PyChor does not verify that the process on the other end is the
party it claims to be, and message contents travel in the clear.

Run a deployment on a trusted network, or inside a tunnel — WireGuard, an SSH
forward, or mutually authenticated TLS — that supplies both properties. Note
that this is a property of the *transport*, not of the protocols: a protocol
like oblivious transfer protects its inputs from the other party, but the
channel still needs protecting from everyone else.

## Writing a custom backend

A backend is a context manager that decides what locating, computing, and
sending mean. Subclass `ChoreographyBackend` and implement seven methods:

| Method | Responsibility |
| --- | --- |
| `constant(party, v)` | Produce a `LocatedVal` owned by `party`. |
| `send(party_from, party_to, lv, note)` | Communicate, add `party_to` to `lv.parties`, and append the value to `views[party_to]`. |
| `locally(f, *args, **kwargs)` | Evaluate `f` at the intersection of its located arguments' owners, and return a value owned by exactly that intersection. |
| `unwrap(lv, parties)` | Return `lv`'s raw value if `parties` may see it, else `None`. |
| `unlist(ls, length)` | Split a located list into `length` located values. |
| `untup(ls, length)` | Split a located tuple into `length` located values. |
| `undict(d, keys)` | Split a located dict into a dict of located values. |

`ChoreographyBackend.__init__` validates the party list and sets up `parties`,
`party_set`, and `views` for you, and `__enter__`/`__exit__` install and clear
the active-backend global. If you override either, call `super()` — otherwise
nothing in the choreography will find your backend.

Two shortcuts are worth taking. `pychor.choreography.get_val` already
implements the argument walk and owner-set intersection that `locally` needs,
so a new backend usually only has to decide whether to *run* `f` after calling
it. And the base class's methods are stubs rather than abstract, so a partial
backend fails by silently returning `None` instead of raising — implement all
seven.

Use `LocalBackend` as the reference implementation for the semantics, and
`TCPBackend` for the pattern of a backend where each process holds only part of
the state.

!!! note
    `ForkingTCPBackend` is deliberately *not* a `ChoreographyBackend` subclass.
    It is a wrapper that forks and then delegates to a real backend, which is a
    good model to follow for a backend that manages processes rather than
    execution semantics.
