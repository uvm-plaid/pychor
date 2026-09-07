# Testing

PyChor's examples are also its test suite. Every example ends with a `check`
call naming the answer it should produce, so running one is enough to know
whether it still works — and `pytest` runs all of them, under every backend,
alongside the tests for the library itself.

## Quick start

```bash
python -m pip install -e ".[examples,test]"
pytest
```

That is the everyday command. It runs **119 tests in about 50 seconds** and
skips the 6 expensive ones. To run everything:

```bash
pytest --runslow
```

**125 tests in about 75 seconds.**

## What the suite covers

| File | Tests | What it checks |
| --- | --- | --- |
| `tests/test_examples.py` | 42 | Every example in `examples/`, under the `local` and `forking_tcp` backends. |
| `tests/test_choreography.py` | 61 | The core API: ownership, where a computation runs, destructuring, operators, views, the sequence diagram. Runs in-process in well under a second. |
| `tests/test_tcp_backend.py` | 18 | `TCPBackend` and `ForkingTCPBackend` — constructor validation, and the SPMD rule that a non-owning process holds `None`. |
| `tests/test_deployment.py` | 4 | Real deployments: one operating-system process per party over real sockets. |

Because the examples assert their own results, a passing run means every
protocol computed the right answer — not merely that it did not crash.

## Selecting tests

```bash
pytest                               # the fast suite
pytest --runslow                     # everything
pytest -k protocol_gmw               # one example, both backends
pytest -k "protocol_gmw and local"   # one example, one backend
pytest tests/test_choreography.py    # just the library tests
pytest -m tcp --runslow              # just the multi-process deployment tests
pytest -x                            # stop at the first failure
pytest --durations=10                # find the slow tests
```

A failing example test prints that example's own stdout and stderr, so the
assertion that failed and the protocol output leading up to it are both in the
report.

## Markers

Two markers are registered, and both are skipped unless you pass `--runslow`:

| Marker | Tests | Why it is slow |
| --- | --- | --- |
| `slow` | 2 | The full statistical run of `protocol_sum.py`, which enters a backend context 200 times. Under `forking_tcp` that means 200 rounds of forking and port binding — about 16 seconds. |
| `tcp` | 4 | Deployment tests, which launch one process per party and wait for a TCP mesh to form. |

The everyday suite still runs `protocol_sum.py`; it just uses a smaller sample.
`PYCHOR_SUM_RUNS` controls the sample size (default 20, and the slow test asks
for 100), so nothing is left untested by the fast run — only measured less
precisely.

## How the example tests work

Each example is run as a **subprocess** rather than imported. That is
deliberate:

- `ForkingTCPBackend` forks one process per party, and the children exit with
  `os._exit` when they leave the backend context. Running that inside the pytest
  process would fork pytest itself.
- A fresh interpreter gives every run clean module-level state, which matters
  because some examples keep a pool of Beaver triples in a module global.
- It is how a reader actually runs an example, so the test exercises the same
  path the documentation describes.

The backend comes from the `PYCHOR_BACKEND` environment variable, which
`examples/example_backend.py` reads — see
[Writing backend-agnostic choreographies](backends.md#writing-backend-agnostic-choreographies).
Ports are handed out by `port_for` in `tests/conftest.py`, which gives each
example its own 100-port window and offsets the whole range per `pytest-xdist`
worker so that parallel runs stay disjoint.

## Asserting inside an example

Examples cannot use a bare `assert`, because under a TCP backend a located value
is `None` in every process whose party does not own it. `example_backend.check`
handles that: it compares the value where the local party is an owner, and does
nothing in the processes that cannot see it.

```python
from example_backend import backend, check

with backend(parties=[p1, p2]):
    x = 5 @ p1
    x.send(src=p1, dest=p2)
    z = 6 @ p2
    y = pychor.locally(lambda a, b: a + b, x, z)

    check(y, 11, 'sum at p2')
```

Pass `tol` for a fixed-point result, whose encoding is exact only up to its
scale factor:

```python
check(result, 5852 / 112, 'average age', tol=1e-6)
```

Note that `==` on two located values is dataclass equality and returns a plain
`bool`, so it compares owner sets as well as contents. Always compare against
the value, which is what `check` does.

## Adding an example

1. Write it in `examples/`, taking its backend from
   `example_backend.backend(parties=...)` rather than naming one directly.
2. Give it a `main()` and an `if __name__ == '__main__':` guard, so importing it
   does not run a protocol.
3. Read any data file relative to `Path(__file__).parent`, so it runs from any
   directory.
4. End with `check` calls on the values it is supposed to produce.
5. Add its filename to `EXAMPLES` in `tests/test_examples.py`.

Step 5 is enforced: `test_examples_list_is_complete` compares the list against
the `protocol_*.py` and `application_*.py` files on disk and fails if they have
drifted apart, so a new example cannot be silently left untested.
