# Examples

The `examples/` directory in the repository holds working choreographies for
real cryptographic protocols. They are the best demonstration of what
choreographic programming buys you: a multi-round MPC protocol reads as a
single Python function, with the communication written down where it happens.

Every example checks its own result. Each one ends with a `check` call naming
the answer it should produce — `check(product, 3 * 4, 'product')` — so the
expected value is part of the example, and running a file is enough to know
whether it still works.

## Running the examples

Install the examples extra and run any example directly:

```bash
python -m pip install -e ".[examples]"
python examples/protocol_beaver.py
```

Choose a backend with `PYCHOR_BACKEND`, since every example goes through
`example_backend.backend`:

```bash
PYCHOR_BACKEND=forking_tcp python examples/protocol_beaver.py
```

## Running them as tests

Because every example checks its own result, the examples are the test suite:

```bash
python -m pip install -e ".[examples,test]"
pytest
```

That runs all of them under both the `simulation` and `forking_tcp` backends,
alongside the tests for the library itself, so a passing run means every
protocol computed the right answer rather than merely not crashing.
`pytest --runslow` adds the full statistical run and the multi-process
deployment tests.

See [Testing](testing.md) for the rest — selecting individual examples, what
each part of the suite covers, and how to add a new example to it.

## Protocols

These are backend-agnostic: each runs under all three backends.

| Example | What it implements |
| --- | --- |
| `protocol_simple.py` | The smallest complete choreography — locate a value, send it, compute jointly, send the result back. Start here. |
| `protocol_commit.py` | A hash-based commitment scheme. A `Commitment` object commits on construction and reveals on `open()`, and it demonstrates `send(note=...)` for labelling messages whose contents are opaque. |
| `protocol_mpc_add.py` | Two-party additive secret sharing over a prime field. An `MPCVal` dataclass holds one share per party and defines `__add__`, so summing shared values looks like ordinary arithmetic. |
| `protocol_beaver.py` | Beaver-triple multiplication: a dealer distributes correlated randomness, then two parties multiply their shared values with one round of communication. The building block for the applications below. |
| `protocol_mult.py` | BGW multiplication of Shamir-shared values. Multiplying shares doubles the degree of the underlying polynomial, so the parties re-share their local products and take a fixed linear combination to bring the degree back down. |
| `protocol_ot.py` | 1-out-of-4 oblivious transfer using PyNaCl sealed boxes. The receiver learns one option and the sender learns nothing about which. A good illustration of ownership doing real work — see [Where a computation runs](concepts.md#where-a-computation-runs). |
| `protocol_ot_mult.py` | Multiplying shared bits with oblivious transfer. Each cross term is computed by offering a two-row table masked with fresh randomness, so the mask cancels once all the terms are summed. |
| `protocol_gmw.py` | GMW secure circuit evaluation over a Bristol-format boolean circuit, evaluating the 64-bit adder in `adder64.txt` gate by gate. XOR gates are free; each of the 63 AND gates costs one oblivious transfer. Ends with an [execution timing](concepts.md#execution-timing) summary at 100 ms per message, which shows the AND gates dominating. |
| `protocol_bgw.py` | BGW evaluation of an arithmetic circuit on Shamir-shared inputs, chaining additions and multiplications so the result depends on all six parties' inputs. Also ends with an execution timing summary at 100 ms per message. |
| `protocol_sum_poly.py` | An n-party sum by additive secret sharing, in three rounds: share, sum locally, broadcast the subtotals. |
| `protocol_sum_poly_shamir.py` | The same sum over Shamir shares. The choreography is identical; only reconstruction differs. |
| `protocol_sum_poly_shamir_vec.py` | The Shamir sum batched over a vector of 20 secrets at once, showing that the protocol shape does not change when it carries more data. |
| `protocol_sum.py` | A three-party sum protocol *plus its security proof* — the ideal functionality, simulator hybrids, and chi-square and Spearman tests comparing real and simulated views. See [Views and security proofs](concepts.md#views-and-security-proofs). |
| `protocol_sum_proof.py` | A hand-written simulation proof for the two-party sum, as a chain of six hybrids you can read side by side, each one step closer to a simulator that never touches the honest input. |
| `protocol_sum3_proof.py` | The same argument for three parties, where the two honest subtotals leave the simulator a degree of freedom: it picks one at random and solves for the other. |

## Applications

These build a secure-datatype layer on top of `protocol_beaver.py`: a Python
class wrapping secret shares, with operators that run sub-protocols. It is the
pattern to copy for anything larger than a single protocol, because it lets
application code be written against ordinary-looking arithmetic.

| Example | What it does |
| --- | --- |
| `application_beaver.py` | `SecInt`, a secret-shared integer supporting `+` and `*` — multiplication consumes a pre-generated Beaver triple — and `reveal()`. |
| `application_fixedpoint.py` | `SecDec`, fixed-point decimals over the same protocol, truncating after each multiplication. |
| `application_division.py` | `SecFp` plus secure division: the reciprocal of the denominator is computed by Newton-Raphson iteration using only addition and multiplication. Computes the average age of heart-disease patients across two parties' private data. |
| `application_integer_heartdisease.py` | A secure 2×2 contingency table over `heart1.csv` and `heart2.csv` using `SecInt`. |

`heart.csv` is the UCI heart-disease dataset; `heart1.csv` and `heart2.csv` are
disjoint halves standing in for two hospitals' private records.

!!! note "Fixed-point arithmetic has an exponent budget"
    `SecFp` scales each value by a power of ten, and multiplying two values adds
    their exponents. The encoded value has to stay inside the field, so the
    exponent — not convergence — is what bounds the number of Newton iterations
    `application_division.py` can afford. Real fixed-point MPC solves this with
    a truncation protocol that rescales a shared value back down; the module
    docstring works through the arithmetic.

## Supporting files

| File | Purpose |
| --- | --- |
| `example_backend.py` | Selects a backend from the environment, and provides the `check` helper the examples use to assert their results and the `print_timing_summary` helper that reports execution timing under `SimulationBackend` only. See [Writing backend-agnostic choreographies](backends.md#writing-backend-agnostic-choreographies). |
| `shamir.py` | Standalone Shamir secret sharing over a prime field — `share`, `reconstruct`, `add`, `mult`, `sum` — with its own self-test. No PyChor dependency. |
| `adder64.txt` | A Bristol-format 64-bit adder circuit, consumed by `protocol_gmw.py`. |
