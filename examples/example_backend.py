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

    raise ValueError(
        f"Unsupported PYCHOR_BACKEND {backend_name!r}; "
        "expected 'local', 'forking_tcp', or 'tcp'"
    )


def _tcp_backend(parties):
    me_name = os.environ.get('PYCHOR_TCP_ME')
    if me_name is None:
        raise ValueError('PYCHOR_TCP_ME is required for PYCHOR_BACKEND=tcp')

    address_spec = os.environ.get('PYCHOR_TCP_ADDRESSES')
    if address_spec is None:
        raise ValueError('PYCHOR_TCP_ADDRESSES is required for PYCHOR_BACKEND=tcp')

    party_by_name = {party.name: party for party in parties}
    me = _party_by_name(party_by_name, me_name)
    addresses = _parse_addresses(party_by_name, address_spec)
    connect_timeout = float(os.environ.get('PYCHOR_TCP_CONNECT_TIMEOUT', '10.0'))

    return pychor.TCPBackend(
        parties=parties,
        me=me,
        addresses=addresses,
        connect_timeout=connect_timeout,
    )


def _parse_addresses(party_by_name, address_spec):
    addresses = {}
    for entry in address_spec.split(','):
        entry = entry.strip()
        if not entry:
            continue

        try:
            party_name, raw_address = entry.split('=', 1)
            host, raw_port = raw_address.rsplit(':', 1)
        except ValueError as exc:
            raise ValueError(
                'PYCHOR_TCP_ADDRESSES entries must use party=host:port'
            ) from exc

        party = _party_by_name(party_by_name, party_name.strip())
        addresses[party] = (host.strip(), int(raw_port))

    return addresses


def _party_by_name(party_by_name, name):
    try:
        return party_by_name[name]
    except KeyError as exc:
        raise ValueError(f'Unknown party name {name!r}') from exc
