import os

import pychor


def check(located, expected, label=None, tol=None):
    """Assert that a located value equals `expected`, wherever it is visible.

    Examples use this instead of a bare `assert` so that they work under every
    backend. Under `LocalBackend` a single process plays every party, so every
    value is present and this always checks. Under a TCP backend each party runs
    in its own process and holds `None` for the values it does not own, so this
    checks only in the processes whose party is an owner and is a no-op in the
    rest.

    Args:
        located: The `LocatedVal` to check.
        expected: The value it should hold.
        label: Optional name for this check, used in the failure message.
        tol: Optional absolute tolerance. Pass this for the fixed-point examples,
            whose encoding is exact only up to the scale factor they use.

    Raises:
        AssertionError: If the local party owns the value and it differs from
            `expected`.
    """
    from pychor import choreography

    me = getattr(choreography.cc, 'party', None)  # None under LocalBackend
    if me is not None and me not in located.parties:
        return

    if tol is not None:
        difference = abs(located.val - expected)
        ok = bool(difference.max() <= tol) if hasattr(difference, 'max') \
            else bool(difference <= tol)
        detail = f'expected {expected} +/- {tol}'
    else:
        # galois scalars and arrays compare elementwise and return numpy values.
        result = located.val == expected
        ok = bool(result.all()) if hasattr(result, 'all') else bool(result)
        detail = f'expected {expected}'

    assert ok, f'{label or "check"}: {detail}, got {located.val}'


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
