import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
BACKENDS = ('local', 'forking_tcp', 'forking_tcp_async')


def test_env(backend, test_index):
    env = os.environ.copy()
    env['PYCHOR_BACKEND'] = backend
    env['PYCHOR_TCP_BASE_PORT'] = str(10000 + test_index * 100)
    return env


def discover_tests():
    return sorted(
        test
        for test in EXAMPLES_DIR.glob('protocol_*.py')
        if 'broken' not in test.name
    )


def main():
    broken = []

    for test_index, test in enumerate(discover_tests()):
        for backend in BACKENDS:
            print('==================================================')
            print(f'Running test: {test.name} [{backend}]')
            try:
                subprocess.run(
                    [sys.executable, test.name],
                    cwd=EXAMPLES_DIR,
                    env=test_env(backend, test_index),
                    check=True,
                )
            except subprocess.CalledProcessError:
                print(f'error in python file for {test.name} [{backend}]!!')
                broken.append((backend, test.name))

    print(f'Broken tests: {broken}')
    return 1 if broken else 0


sys.exit(main())
