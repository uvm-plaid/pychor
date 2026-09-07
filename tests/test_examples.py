"""Run every example, under every backend it supports.

The examples check their own results with `example_backend.check`, so these
tests only have to run them and require a zero exit status. That keeps the
expected answers next to the code that computes them, where a reader will see
them, instead of duplicated here.
"""

import pytest

from conftest import port_for, run_example

# Backends every example is expected to work under. The `tcp` deployment
# backend needs one process per party and is exercised in test_deployment.py.
BACKENDS = ['local', 'forking_tcp']

# Every runnable example, in the order the port windows are handed out. `slow`
# examples are skipped unless --runslow is given.
EXAMPLES = [
    # Protocols.
    'protocol_simple.py',
    'protocol_commit.py',
    'protocol_ot.py',
    'protocol_mpc_add.py',
    'protocol_beaver.py',
    'protocol_gmw.py',
    'protocol_sum.py',
    'protocol_mult.py',
    'protocol_bgw.py',
    'protocol_ot_mult.py',
    'protocol_sum_poly.py',
    'protocol_sum_poly_shamir.py',
    'protocol_sum_poly_shamir_vec.py',
    'protocol_sum_proof.py',
    'protocol_sum3_proof.py',
    # Applications built on top of the protocols.
    'application_beaver.py',
    'application_fixedpoint.py',
    'application_division.py',
    'application_integer_heartdisease.py',
]

PORTS = {name: port_for(i) for i, name in enumerate(EXAMPLES)}


@pytest.mark.parametrize('backend', BACKENDS)
@pytest.mark.parametrize('example', EXAMPLES)
def test_example(example, backend):
    run_example(example, backend=backend, base_port=PORTS[example])


def test_shamir_helpers():
    """shamir.py is a plain library with its own self-test, and no backend."""
    run_example('shamir.py')


@pytest.mark.slow
@pytest.mark.parametrize('backend', BACKENDS)
def test_sum_proof_statistics(backend):
    """The statistical part of protocol_sum.py, at a real sample size.

    The default run uses a small sample so the suite stays fast. This runs the
    sample size the distribution comparison actually wants.
    """
    run_example(
        'protocol_sum.py',
        backend=backend,
        base_port=port_for(len(EXAMPLES)),
        env={'PYCHOR_SUM_RUNS': '100'},
    )


def test_examples_list_is_complete(examples_dir):
    """Fail if someone adds an example and forgets to register it here."""
    on_disk = {
        path.name
        for path in examples_dir.glob('*.py')
        if path.name.startswith(('protocol_', 'application_'))
    }
    missing = on_disk - set(EXAMPLES)
    assert not missing, f'examples not covered by the test suite: {sorted(missing)}'

    stale = set(EXAMPLES) - on_disk
    assert not stale, f'examples listed but not on disk: {sorted(stale)}'
