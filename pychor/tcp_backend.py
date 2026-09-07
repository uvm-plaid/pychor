"""TCP backends for running choreographies over object streams.

This module provides the two backends that execute a choreography with one
party per operating-system process:

- `TCPBackend` is the deployment backend. Each party runs the same program in
  its own process, on its own machine, and the processes connect to each other
  over TCP.
- `ForkingTCPBackend` is the localhost testing backend. It forks a process per
  party on one machine and wires them together with `TCPBackend`, so a
  choreography can be exercised one-party-per-process without any deployment.

Both use `pychor.object_stream.ObjectStream` as the wire format.

## Execution model

These backends run in an SPMD ("single program, multiple data") style: every
party executes the *same* choreography, and each process keeps only the values
its own party is entitled to see. A located value's owner set is identical in
every process, because it is derived from the program text; its *contents* are
not. `LocatedVal.val` holds the real value only where the local party is an
owner, and is `None` everywhere else.

The practical consequence is that a choreography may branch on ownership but
not on data. Testing `if alice in x.parties:` is well defined — every process
computes the same answer, so they all take the same branch and stay in step.
Testing `if x.val > 0:` is not, because the value is `None` in the processes
that do not own it, so the processes would disagree about the branch and
deadlock on the next send. To make a value available for a decision, send it.

## Security

`ObjectStream` frames pickled Python objects, and unpickling executes arbitrary
code from the sender. These backends provide no authentication and no
encryption, so a deployment must run over a trusted network — or inside a
tunnel that supplies both.
"""

import os
import socket
import sys
import time
from collections.abc import Mapping
from typing import Any, Callable, Iterable, Optional, Set

from . import object_stream
from .choreography import (
    ChoreographyBackend,
    LocatedVal,
    Party,
    _intersect_party_sets,
    _validate_parties,
    get_val,
)


class TCPBackend(ChoreographyBackend):
    """Run one party of a choreography over TCP.

    This backend does not fork. Each party should run the same choreography
    program in a separate Python process, passing its local party as `me` and a
    shared address map for all parties.

    Every process must agree on the `parties` list *and its order*, because the
    order determines which side of each connection dials and which listens.
    Entering the context establishes a full mesh between all parties and blocks
    until it is complete, so the processes may be started in any order as long
    as they all start within `connect_timeout`.

    Only this process's own party's values are materialized: `constant` and
    `locally` produce `None` for values this party does not own, and `send`
    transfers the real value to the destination process. See the module
    documentation for what that means for control flow.

    Attributes:
        party: The party this process is playing, as passed in `me`.
        party_index: That party's position in `parties`.
        addresses: The validated address map.
        streams: One `ObjectStream` per remote party, valid inside the context.

    Args:
        parties: All parties in the choreography, in an order every process
            agrees on. Names must be unique.
        me: The party this process plays. Must appear in `parties`.
        addresses: Maps every party to the `(host, port)` its process listens
            on. Must cover exactly `parties` — no missing and no unknown
            parties. Each party binds its own entry, so the hosts must be
            addresses the corresponding process can bind and the others can
            reach.
        connect_timeout: Seconds to spend establishing the mesh before raising
            `TimeoutError`. This bounds the whole setup, so it doubles as the
            window in which every party's process must have started.

    Raises:
        TypeError: If `me` is not a `Party`, or `addresses` is malformed.
        ValueError: If `me` is not part of `parties`, or `addresses` does not
            cover exactly `parties`.

    Example:
        Run this once per party, changing only `me`:

        ```python
        addresses = {
            alice: ("10.0.0.1", 10000),
            bob: ("10.0.0.2", 10000),
        }

        with pychor.TCPBackend(parties=[alice, bob], me=alice, addresses=addresses):
            x = 5 @ alice
            x.send(src=alice, dest=bob)
        ```
    """

    def __init__(
        self,
        parties: Iterable[Party],
        *,
        me: Party,
        addresses: Mapping[Party, tuple[str, int]],
        connect_timeout: float = 10.0,
    ):
        super().__init__(parties)
        if not isinstance(me, Party):
            raise TypeError('me must be a Party')
        if me not in self.party_set:
            raise ValueError(f'Party {me} is not part of this backend')

        self.party = me
        self.party_index = self.parties.index(me)
        self.addresses = self._validate_addresses(addresses)
        self.connect_timeout = connect_timeout
        self.streams = {}
        self.server_socket = None

    def __enter__(self):
        """Establish the party mesh, then become the active backend.

        Raises:
            TimeoutError: If the mesh is not complete within `connect_timeout`.
        """
        self._connect_all()
        return super().__enter__()

    def __exit__(self, exception_type, exception_value, traceback):
        """Close every connection, then stand down as the active backend."""
        self._close_network()
        super().__exit__(exception_type, exception_value, traceback)
        return False

    def constant(self, party: Party, v: Any) -> LocatedVal:
        """Create a located value, materialized only in its owning process.

        Every process creates a located value with the same owner set, but only
        the process playing `party` stores `v`; the others store `None`.

        Args:
            party: The owning party.
            v: The value, which is ignored in processes other than `party`'s.

        Returns:
            A located value owned by `party`.

        Raises:
            ValueError: If `party` is not part of this backend.
        """
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
        """Send a located value from one party process to another.

        This is a synchronization point between exactly two processes: the
        sender writes the value to its stream and the receiver blocks until it
        arrives. Every process — including uninvolved ones — adds `party_to` to
        the owner set, so all processes keep identical ownership information.

        A send from a party to itself moves no data.

        Args:
            party_from: The sending party, which must already own `lv`.
            party_to: The receiving party.
            lv: The located value to send. The receiving process fills in its
                `val` in place.
            note: Accepted for interface compatibility with `SimulationBackend`;
                these backends draw no diagram, so it is unused.
        """
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
        """Evaluate `f` in every process that can observe all located inputs.

        The owner set of the result is computed identically in every process,
        but `f` itself runs only where the local party is one of those owners.
        Elsewhere the call is skipped and the result holds `None`.

        Args:
            f: An ordinary Python function.
            *args: Located values, plain scalars, or containers of those.
            **kwargs: Keyword arguments, handled the same way.

        Returns:
            A located value owned by the parties that could see every located
            input.

        Raises:
            AssertionError: If the located arguments have no owner in common.
        """
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
        """Return this process's raw value when it belongs to `parties`.

        Returns:
            The underlying value, or `None` if the requested parties are not all
            owners or if this process's party is not among them.
        """
        assert isinstance(lv, LocatedVal)
        if isinstance(parties, Party):
            parties = {parties}
        if parties.issubset(lv.parties) and self.party in parties:
            return lv.val
        return None

    def unlist(self, ls, length):
        """Split a located list, using `None` placeholders where unowned.

        Non-owning processes have no list to split, so they produce `length`
        located values holding `None` — keeping the structure, and therefore the
        control flow, identical in every process.
        """
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
        """Split a located tuple, using `None` placeholders where unowned."""
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
        """Split a located dict, using `None` placeholders where unowned."""
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
        return self.addresses[self.parties[party_index]]

    def _validate_addresses(self, addresses) -> dict:
        """Check that `addresses` covers exactly this backend's parties.

        Returns:
            A new dict mapping each party, in `parties` order, to a validated
            `(host, port)` tuple.

        Raises:
            TypeError: If `addresses` is not a mapping, or an entry is not a
                `(str, int)` pair.
            ValueError: If a party is missing or an unknown party is present.
        """
        if not isinstance(addresses, Mapping):
            raise TypeError('addresses must be a mapping from Party to (host, port)')

        missing = [party for party in self.parties if party not in addresses]
        if missing:
            raise ValueError(f'addresses missing parties: {missing}')

        extras = [party for party in addresses if party not in self.party_set]
        if extras:
            raise ValueError(f'addresses includes unknown parties: {extras}')

        validated = {}
        for party in self.parties:
            address = addresses[party]
            if not isinstance(address, tuple) or len(address) != 2:
                raise TypeError(
                    f'address for {party} must be a (host, port) tuple'
                )

            host, port = address
            if not isinstance(host, str):
                raise TypeError(f'host for {party} must be a string')
            if not isinstance(port, int):
                raise TypeError(f'port for {party} must be an int')
            validated[party] = (host, port)

        return validated

    def _connect_all(self):
        """Build a full mesh of connections to every other party.

        The party order in `parties` breaks the symmetry that would otherwise
        make two processes dial each other simultaneously: each party listens on
        its own address and **accepts** one connection from every
        lower-indexed party, then **dials** every higher-indexed party. Each
        dialing party sends its own index as a handshake so the accepting side
        can tell which stream belongs to whom, since connections may arrive in
        any order.

        The whole procedure is bounded by `connect_timeout`, and the listening
        socket is closed once the mesh is up.

        Raises:
            TimeoutError: If the mesh is not complete before the deadline.
            RuntimeError: If a peer sends an invalid or unexpected handshake.
        """
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
            if not 0 <= remote_index < self.party_index:
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
        """Accept one incoming connection, polling until `deadline`."""
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
        """Dial one party, retrying every 50ms until `deadline`."""
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
        """Close every peer stream and the listening socket."""
        for stream in self.streams.values():
            stream.close()
        self.streams = {}

        if self.server_socket is not None:
            self.server_socket.close()
            self.server_socket = None


class ForkingTCPBackend:
    """Run all parties as forked local processes connected by TCP.

    This is the testing counterpart to `TCPBackend`: it gives a choreography
    genuine one-party-per-process execution without any deployment, so it
    catches protocols that only work because `SimulationBackend` happens to hold
    every party's data in one place.

    Entering the context forks one child per party after the first — the parent
    plays `parties[0]` — and each process then enters a `TCPBackend` for its own
    party. Parties are assigned deterministic localhost ports by their order in
    `parties`: the first party uses `base_port`, the second uses
    `base_port + 1`, and so on.

    Two details are worth knowing. First, this class is a context-manager
    wrapper rather than a `ChoreographyBackend` subclass, and `__enter__`
    returns the inner `TCPBackend`; so `with ForkingTCPBackend(...) as b` binds
    `b` to that backend, whose `views` contain only the local party's messages.
    Second, the code inside the `with` block runs once per party, in different
    processes — so its output is interleaved, and side effects such as writing
    files happen once per party.

    On a clean exit each child flushes its output and exits immediately, while
    the parent waits for all children and raises `RuntimeError` if any of them
    failed. A child's traceback appears on stderr as usual.

    Args:
        parties: All parties in the choreography. Order fixes the port
            assignment and decides which party the parent process plays.
        host: Address every party binds and connects to.
        base_port: Port of the first party; party *i* uses `base_port + i`.
            Concurrent runs need non-overlapping windows —
            the test suite gives each example its own 100-port range.
        connect_timeout: Seconds to spend establishing the mesh before raising
            `TimeoutError`.

    Raises:
        RuntimeError: On entry, if the platform has no `os.fork`; on exit, if a
            child process failed.

    Example:
        ```python
        with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=10100):
            x = 5 @ alice
            x.send(src=alice, dest=bob)
        ```
    """

    def __init__(
        self,
        parties: Iterable[Party],
        host: str = '127.0.0.1',
        base_port: int = 10000,
        connect_timeout: float = 10.0,
    ):
        self.parties = _validate_parties(parties)
        self.host = host
        self.base_port = base_port
        self.connect_timeout = connect_timeout
        self.party = None
        self.party_index = None
        self.child_pids = []
        self.is_child = False
        self.backend = None

    def __enter__(self) -> 'TCPBackend':
        """Fork one process per party and enter a `TCPBackend` in each.

        Returns:
            The inner `TCPBackend` for this process's party — not this wrapper.

        Raises:
            RuntimeError: If the platform does not provide `os.fork`.
            TimeoutError: If the party mesh cannot be established.
        """
        if not hasattr(os, 'fork'):
            raise RuntimeError(
                'ForkingTCPBackend requires os.fork and a Unix-like platform'
            )

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

        addresses = {
            party: (self.host, self.base_port + index)
            for index, party in enumerate(self.parties)
        }
        self.backend = TCPBackend(
            self.parties,
            me=self.party,
            addresses=addresses,
            connect_timeout=self.connect_timeout,
        )
        return self.backend.__enter__()

    def __exit__(self, exception_type, exception_value, traceback):
        """Tear down this process's backend and reap the forked children.

        In a child, this never returns on a clean exit: the child flushes its
        streams and exits so that it does not continue running the rest of the
        enclosing program. In the parent, it waits for every child and surfaces
        their failures.

        Raises:
            RuntimeError: In the parent, if a child exited non-zero and no
                exception is already propagating.
        """
        if self.backend is not None:
            self.backend.__exit__(exception_type, exception_value, traceback)

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
            raise RuntimeError(f'ForkingTCPBackend child process failures: {failures}')
        return False
