"""TCP backend for running a choreography as local party processes."""

import os
import socket
import sys
import time
from typing import Any, Callable, Optional, Set

from . import object_stream
from .choreography import (
    ChoreographyBackend,
    LocatedVal,
    Party,
    _intersect_party_sets,
    get_val,
)


class TCPBackend(ChoreographyBackend):
    """Run a choreography across forked local processes connected by TCP.

    Parties are assigned deterministic localhost ports by their order in
    `parties`: the first party uses `base_port`, the second uses
    `base_port + 1`, and so on.
    """

    def __init__(
        self,
        parties,
        host: str = '127.0.0.1',
        base_port: int = 10000,
        connect_timeout: float = 10.0,
    ):
        super().__init__(parties)
        self.host = host
        self.base_port = base_port
        self.connect_timeout = connect_timeout
        self.party = None
        self.party_index = None
        self.streams = {}
        self.server_socket = None
        self.child_pids = []
        self.is_child = False

    def __enter__(self):
        if not hasattr(os, 'fork'):
            raise RuntimeError('TCPBackend requires os.fork and a Unix-like platform')

        self.child_pids = []
        for party_index in range(1, len(self.parties)):
            pid = os.fork()
            if pid == 0:
                self.party_index = party_index
                self.party = self.parties[party_index]
                self.child_pids = []
                self.is_child = True
                break
            self.child_pids.append(pid)
        else:
            self.party_index = 0
            self.party = self.parties[0]
            self.is_child = False

        self._connect_all()
        return super().__enter__()

    def __exit__(self, exception_type, exception_value, traceback):
        self._close_network()
        super().__exit__(exception_type, exception_value, traceback)

        if self.is_child:
            if exception_type is None:
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(0)
            return False

        failures = []
        for pid in self.child_pids:
            while True:
                try:
                    _, status = os.waitpid(pid, 0)
                    break
                except InterruptedError:
                    continue
            if status != 0:
                failures.append((pid, status))

        if exception_type is None and failures:
            raise RuntimeError(f'TCPBackend child process failures: {failures}')
        return False

    def constant(self, party: Party, v: Any) -> LocatedVal:
        """Create a located value, materialized only in its owning process."""
        if party not in self.party_set:
            raise ValueError(f'Party {party} is not part of this backend')
        return LocatedVal({party}, v if party == self.party else None)

    def send(
        self,
        party_from: Party,
        party_to: Party,
        lv: LocatedVal,
        note: Optional[str] = None,
    ) -> None:
        """Send a located value from one party process to another."""
        assert isinstance(lv, LocatedVal)
        assert isinstance(party_from, Party)
        assert isinstance(party_to, Party)
        assert party_from in lv.parties

        if party_from == party_to:
            if self.party == party_to:
                self.views[party_to].append(lv.val)
            lv.parties.add(party_to)
            return

        if self.party == party_from:
            val = self.unwrap(lv, {party_from})
            self.streams[party_to].put_obj(val)
        elif self.party == party_to:
            val = self.streams[party_from].get_obj()
            object.__setattr__(lv, 'val', val)
            self.views[party_to].append(val)

        lv.parties.add(party_to)

    def locally(self, f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
        """Evaluate `f` in every process that can observe all located inputs."""
        new_args, args_parties = get_val(args)
        new_kwargs, kwargs_parties = get_val(kwargs) if kwargs else ({}, None)
        new_parties = _intersect_party_sets(
            [args_parties, kwargs_parties],
            f'No participating parties for {args}',
        )

        if self.party in new_parties:
            output = f(*new_args, **new_kwargs)
        else:
            output = None
        return LocatedVal(new_parties.copy(), output)

    def unwrap(self, lv: LocatedVal, parties: Set[Party]) -> Any:
        """Return this process's raw value when it belongs to `parties`."""
        assert isinstance(lv, LocatedVal)
        if isinstance(parties, Party):
            parties = {parties}
        if parties.issubset(lv.parties) and self.party in parties:
            return lv.val
        return None

    def unlist(self, ls, length):
        assert isinstance(length, int)
        assert isinstance(ls, LocatedVal)

        parties = ls.parties
        if self.party in parties:
            assert isinstance(ls.val, list)
            assert len(ls.val) == length
            values = ls.val
        else:
            values = [None for _ in range(length)]
        return [LocatedVal(parties.copy(), x) for x in values]

    def untup(self, ls, length):
        assert isinstance(length, int)
        assert isinstance(ls, LocatedVal)

        parties = ls.parties
        if self.party in parties:
            assert isinstance(ls.val, tuple)
            assert len(ls.val) == length
            values = ls.val
        else:
            values = tuple(None for _ in range(length))
        return tuple(LocatedVal(parties.copy(), x) for x in values)

    def undict(self, d, keys):
        assert isinstance(d, LocatedVal)

        parties = d.parties
        if self.party in parties:
            assert isinstance(d.val, dict)
            assert set(d.val.keys()) == set(keys)
            values = d.val
        else:
            values = {k: None for k in keys}
        return {k: LocatedVal(parties.copy(), values[k]) for k in keys}

    def _address(self, party_index):
        return (self.host, self.base_port + party_index)

    def _connect_all(self):
        self.streams = {}

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(self._address(self.party_index))
        self.server_socket.listen(max(1, len(self.parties) - 1))
        self.server_socket.settimeout(0.1)

        deadline = time.monotonic() + self.connect_timeout

        for _ in range(self.party_index):
            stream = self._accept_lower_party(deadline)
            remote_index = stream.get_obj()
            if not isinstance(remote_index, int):
                stream.close()
                raise RuntimeError('Invalid TCPBackend party handshake')
            if remote_index >= self.party_index:
                stream.close()
                raise RuntimeError('Unexpected TCPBackend party connection')
            self.streams[self.parties[remote_index]] = stream

        for remote_index in range(self.party_index + 1, len(self.parties)):
            sock = self._connect_to_party(remote_index, deadline)
            stream = object_stream.ObjectStream(sock)
            stream.put_obj(self.party_index)
            self.streams[self.parties[remote_index]] = stream

        self.server_socket.close()
        self.server_socket = None

    def _accept_lower_party(self, deadline):
        while True:
            try:
                sock, _ = self.server_socket.accept()
                return object_stream.ObjectStream(sock)
            except socket.timeout:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f'Timed out accepting TCPBackend connections for {self.party}'
                    )

    def _connect_to_party(self, remote_index, deadline):
        address = self._address(remote_index)
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(address)
            if result == 0:
                return sock
            sock.close()

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f'Timed out connecting {self.party} to {self.parties[remote_index]}'
                )
            time.sleep(0.05)

    def _close_network(self):
        for stream in self.streams.values():
            stream.close()
        self.streams = {}

        if self.server_socket is not None:
            self.server_socket.close()
            self.server_socket = None
