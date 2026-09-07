"""Shared fixtures and helpers for the PyChor test suite.

The example tests run each example as a subprocess rather than importing it.
That is deliberate: `ForkingTCPBackend` forks one process per party and the
children exit with `os._exit` when they leave the backend context, so running it
inside the pytest process would fork pytest itself. A subprocess also matches
how a reader actually runs an example, and gives every run a clean set of
module-level globals.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / 'examples'

# Each example gets its own window of ports so that nothing collides, and the
# whole range is shifted per xdist worker so that parallel runs stay disjoint.
PORT_WINDOW = 100
BASE_PORT = 10000
WORKER_STRIDE = 4000


def pytest_addoption(parser):
    parser.addoption(
        '--runslow',
        action='store_true',
        default=False,
        help='run the slow and multi-process TCP deployment tests',
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption('--runslow'):
        return

    skip_slow = pytest.mark.skip(reason='needs --runslow')
    for item in items:
        if 'slow' in item.keywords or 'tcp' in item.keywords:
            item.add_marker(skip_slow)


def _worker_offset():
    """Shift the port range so that xdist workers do not collide."""
    worker = os.environ.get('PYTEST_XDIST_WORKER')
    if not worker:
        return 0
    digits = ''.join(c for c in worker if c.isdigit())
    return (int(digits) + 1) * WORKER_STRIDE if digits else WORKER_STRIDE


def port_for(index):
    """Return the base port for the example at position `index`."""
    return BASE_PORT + _worker_offset() + index * PORT_WINDOW


def run_example(name, backend='simulation', base_port=None, timeout=300, env=None):
    """Run one example as a subprocess and return the completed process.

    Fails the test with the example's own output attached if it exits non-zero.
    Because the examples assert their own results, a zero exit status is the
    correctness check.
    """
    environment = os.environ.copy()
    environment['PYCHOR_BACKEND'] = backend
    if base_port is not None:
        environment['PYCHOR_TCP_BASE_PORT'] = str(base_port)
    if env:
        environment.update(env)

    completed = subprocess.run(
        [sys.executable, name],
        cwd=EXAMPLES_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if completed.returncode != 0:
        pytest.fail(
            f'{name} failed under the {backend} backend '
            f'(exit {completed.returncode})\n'
            f'--- stdout ---\n{completed.stdout}\n'
            f'--- stderr ---\n{completed.stderr}'
        )
    return completed


@pytest.fixture
def examples_dir():
    return EXAMPLES_DIR


@pytest.fixture
def in_examples_dir(monkeypatch):
    """Run a test with the examples directory as the working directory."""
    monkeypatch.chdir(EXAMPLES_DIR)
    return EXAMPLES_DIR
