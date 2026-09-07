# Examples

The `examples/` directory in the repository holds working choreographies for
real cryptographic protocols. They are the best demonstration of what
choreographic programming buys you: a multi-round MPC protocol reads as a
single Python function, with the communication written down where it happens.

## Running the examples

Install the examples extra and run them from inside the `examples/` directory —
they import `example_backend` as a sibling module, and `protocol_gmw.py` reads
its circuit file by relative path:

```bash
python -m pip install -e ".[examples]"
cd examples
python protocol_beaver.py
```

Choose a backend with `PYCHOR_BACKEND`, since every protocol goes through
`example_backend.backend`:

```bash
PYCHOR_BACKEND=forking_tcp python protocol_beaver.py
```

`run_tests.py` runs the whole suite under both the local and forking-TCP
backends, giving each file its own port window so nothing collides:

```bash
python run_tests.py
```

It discovers every `protocol_*.py`, skips the `broken_*` sketches, and exits
non-zero if any run fails. Because the examples mostly print rather than
assert, a pass means "ran to completion in every party's process" — which for
the TCP backend is a meaningful check on its own, since a choreography that
reads data it does not own will hang or crash there.

## Protocols

These are backend-agnostic: each runs under all three backends.

| Example | What it implements |
| --- | --- |
| `protocol_simple.py` | The smallest complete choreography — locate a value, send it, compute jointly, send the result back. Start here. |
| `protocol_commit.py` | A hash-based commitment scheme. A `Commitment` object commits on construction and reveals on `open()`, and it demonstrates `send(note=...)` for labelling messages whose contents are opaque. |
| `protocol_mpc_add.py` | Two-party additive secret sharing over a prime field. An `MPCVal` dataclass holds one share per party and defines `__add__`, so summing shared values looks like ordinary arithmetic. |
| `protocol_beaver.py` | Beaver-triple multiplication: a dealer distributes correlated randomness, then two parties multiply their shared values with one round of communication. The building block for the applications below. |
| `protocol_ot.py` | 1-out-of-4 oblivious transfer using PyNaCl sealed boxes. The receiver learns one option and the sender learns nothing about which. A good illustration of ownership doing real work — see [Where a computation runs](concepts.md#where-a-computation-runs). |
| `protocol_gmw.py` | GMW secure circuit evaluation over a Bristol-format boolean circuit, evaluating the 64-bit adder in `adder64.txt` gate by gate, with AND gates implemented via `protocol_ot`. |
| `protocol_sum.py` | A three-party sum protocol *plus its security proof* — the ideal functionality, a sequence of simulator hybrids, and statistical tests comparing real and simulated views. See [Views and security proofs](concepts.md#views-and-security-proofs). |

## Applications

These build a secure-datatype layer on top of `protocol_beaver.py`: a Python
class wrapping secret shares, with operators that run sub-protocols. It is the
pattern to copy for anything larger than a single protocol, because it lets
application code be written against ordinary-looking arithmetic. They use
`LocalBackend` directly and are not part of the test suite.

| Example | What it does |
| --- | --- |
| `application_beaver.py` | `SecInt`, a secret-shared integer supporting `+` and `*` — multiplication consumes a pre-generated Beaver triple — and `reveal()`. |
| `application_fixedpoint.py` | `SecDec`, fixed-point decimals over the same protocol, truncating after each multiplication. |
| `application_division.py` | `SecFp` plus secure division by Newton iteration on the reciprocal, computing the average age of heart-disease patients across two parties' private data. |
| `application_integer_heartdisease.py` | A secure 2×2 contingency table over `heart1.csv` and `heart2.csv` using `SecInt`. |

`heart.csv` is the UCI heart-disease dataset; `heart1.csv` and `heart2.csv` are
disjoint halves standing in for two hospitals' private records.

## Supporting files

| File | Purpose |
| --- | --- |
| `example_backend.py` | Selects a backend from the environment. See [Writing backend-agnostic choreographies](backends.md#writing-backend-agnostic-choreographies). |
| `run_tests.py` | Runs every protocol under every tested backend. |
| `shamir.py` | Standalone Shamir secret sharing over a prime field — `share`, `reconstruct`, `add`, `mult`. No PyChor dependency. |
| `adder64.txt` | A Bristol-format 64-bit adder circuit, consumed by `protocol_gmw.py`. |

## Stale sketches

The `broken_*.py` files are kept as design records of protocols that have been
written in PyChor — BGW circuit evaluation, OT-based multiplication, Shamir
sums, zero-knowledge graph colouring, and simulator-based proofs for the sum
protocol. They do **not** run against the current API: they use a `>>` send
operator, a `LocatedVal.party` attribute, and a `LocalBackend(emit_sequence=…)`
argument that no longer exist. `run_tests.py` skips them.

Read them for the protocol structure, not as usable code.
