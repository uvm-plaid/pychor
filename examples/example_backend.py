import os

import pychor


def backend(parties):
    backend_name = os.environ.get('PYCHOR_BACKEND', 'local').lower()

    if backend_name == 'local':
        return pychor.LocalBackend(parties=parties)
    if backend_name == 'tcp':
        base_port = int(os.environ.get('PYCHOR_TCP_BASE_PORT', '10000'))
        return pychor.TCPBackend(parties=parties, base_port=base_port)

    raise ValueError(
        f"Unsupported PYCHOR_BACKEND {backend_name!r}; expected 'local' or 'tcp'"
    )
