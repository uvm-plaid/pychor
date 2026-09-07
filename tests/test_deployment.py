"""Deployment tests: one operating-system process per party, over real sockets.

`TCPBackend` is how a choreography is actually deployed -- each party runs the
same program on its own machine -- but unlike `ForkingTCPBackend` nothing sets
the processes up for you. These tests do what a deployment does: launch one
process per party with its own `PYCHOR_TCP_ME`, and wait for all of them.

Marked `tcp`, so they run with --runslow.
"""

import os
import subprocess
import sys

import pytest

from conftest import EXAMPLES_DIR

pytestmark = pytest.mark.tcp

# (example, party names in the order the example declares them, base port)
DEPLOYMENTS = [
    ('protocol_simple.py', ['party1', 'party2'], 14100),
    ('protocol_commit.py', ['sender', 'receiver'], 14110),
    ('protocol_sum.py', ['p1', 'p2', 'Fsum'], 14120),
]


def deploy(example, party_names, base_port, timeout=180):
    """Run one process per party and return their completed processes.

    Every process gets the same address map -- the parties have to agree on it,
    and on the order of the party list -- and differs only in which party it
    plays.
    """
    addresses = ','.join(
        f'{name}=127.0.0.1:{base_port + i}'
        for i, name in enumerate(party_names)
    )

    processes = []
    for name in party_names:
        environment = os.environ.copy()
        environment.update({
            'PYCHOR_BACKEND': 'tcp',
            'PYCHOR_TCP_ME': name,
            'PYCHOR_TCP_ADDRESSES': addresses,
            'PYCHOR_TCP_CONNECT_TIMEOUT': '30',
        })
        processes.append((name, subprocess.Popen(
            [sys.executable, example],
            cwd=EXAMPLES_DIR,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )))

    results = {}
    for name, process in processes:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            pytest.fail(f'{example} as {name} timed out\n{stdout}\n{stderr}')
        results[name] = (process.returncode, stdout, stderr)

    for name, (code, stdout, stderr) in results.items():
        if code != 0:
            pytest.fail(
                f'{example} as {name} failed (exit {code})\n'
                f'--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}'
            )
    return results


@pytest.mark.parametrize('example, party_names, base_port', DEPLOYMENTS)
def test_deployment(example, party_names, base_port):
    """Every party's process must run the example to completion."""
    results = deploy(example, party_names, base_port)
    assert set(results) == set(party_names)


def test_each_party_sees_only_its_own_data():
    """A deployed choreography really does keep the parties' data apart.

    Running protocol_simple.py one process per party, `party1` starts with the
    value 5 and `party2` does not; the sum is computed at `party2` and is
    unavailable to `party1` until it is sent back. Both processes agree on the
    owner sets throughout.
    """
    results = deploy('protocol_simple.py', ['party1', 'party2'], 14130)

    party1_out = results['party1'][1]
    party2_out = results['party2'][1]

    # The located constant: real at its owner, None everywhere else.
    assert 'x 5@{party1}' in party1_out
    assert 'x None@{party1}' in party2_out

    # The sum is computed where its inputs are, which is party2.
    assert 'y 11@{party2}' in party2_out
    assert 'y None@{party2}' in party1_out

    # After the final send both parties hold it.
    assert party1_out.rstrip().endswith('y 11@{party1, party2}') or \
        party1_out.rstrip().endswith('y 11@{party2, party1}')
