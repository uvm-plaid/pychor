# Installation

## Installing PyChor

Install PyChor from PyPI:

```bash
python -m pip install pychor
```

PyChor requires **Python 3.9 or newer** and has no required dependencies — the
core library and all three backends are built from the standard library alone.

For local development, install the package from a checkout:

```bash
python -m pip install -e .
```

## Optional extras

The bundled examples implement real cryptographic protocols and need a few
third-party packages. Install the `examples` extra to run them:

```bash
python -m pip install -e ".[examples]"
```

That pulls in `galois` (finite-field arithmetic for secret sharing), `pynacl`
(public-key encryption, used by the oblivious-transfer protocol), and `numpy`,
`scipy`, `pandas`, and `matplotlib` for the applications and the statistical
security tests. See [Examples](examples.md) for what each example needs.

## Running the tests

The examples double as the test suite. Install the test extra and run `pytest`
from a checkout:

```bash
python -m pip install -e ".[examples,test]"
pytest
```

`pytest` runs every example under the `local` and `forking_tcp` backends, plus
the tests for the library itself; `pytest --runslow` adds the long statistical
run and the multi-process deployment tests. See [Testing](testing.md) for what
the suite covers and how to select parts of it.

## Platform requirements

The backends differ in what they ask of the platform:

| Backend | Requirement |
| --- | --- |
| `LocalBackend` | None. Runs anywhere Python runs. |
| `ForkingTCPBackend` | `os.fork`, so Unix-like systems only — not Windows. Needs `len(parties)` free localhost ports starting at `base_port`. |
| `TCPBackend` | Each party's address must be bindable by its own process and reachable from every other party, with the chosen ports open. |

Both TCP backends move data as pickled Python objects with no authentication or
encryption, so they belong on a trusted network. See
[Backends](backends.md#security) for the details.

## Building the documentation

To build this documentation locally, install the documentation extra:

```bash
python -m pip install -e ".[docs]"
```

Preview the documentation site:

```bash
mkdocs serve
```

Validate a production build:

```bash
mkdocs build --strict
```

Deploy the documentation manually to GitHub Pages:

```bash
mkdocs gh-deploy --clean
```
