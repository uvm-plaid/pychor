"""TCP backends for running choreographies over object streams."""

import os
import socket
import sys
import time
import threading
from collections import defaultdict
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any, Callable, Optional, Set

from . import object_stream
from .choreography import (
    ChoreographyBackend,
    LocatedVal,
    Party,
    _intersect_party_sets,
    _validate_parties,
    _validate_first_values,
    get_val,
)


_ASYNC_ENVELOPE_TYPE = 'pychor.tcp_async.v1'


class AsyncValue:
    """A future value used by TCPAsyncBackend."""

    def __init__(self, future=None, compute=None, label='async value'):
        if future is None and compute is None:
            raise ValueError('future or compute is required')
        self._future = future
        self._compute = compute
        self.label = label
        self._condition = threading.Condition()
        self._started = False
        self._done = False
        self._value = None
        self._exception = None

    def result(self):
        if self._future is not None:
            return self._future.result()

        should_compute = False
        with self._condition:
            if self._done:
                return self._return_result()
            if not self._started:
                self._started = True
                should_compute = True
            else:
                while not self._done:
                    self._condition.wait()
                return self._return_result()

        if should_compute:
            try:
                value = self._compute()
            except BaseException as exc:
                with self._condition:
                    self._exception = exc
                    self._done = True
                    self._condition.notify_all()
                raise

            with self._condition:
                self._value = value
                self._done = True
                self._condition.notify_all()
                return self._return_result()

    def _return_result(self):
        if self._exception is not None:
            raise self._exception
        return self._value

    def __repr__(self):
        if self._future is not None:
            if not self._future.done():
                return f'<AsyncValue pending: {self.label}>'
            if self._future.exception() is not None:
                return f'<AsyncValue failed: {self.label}>'
            return f'<AsyncValue done: {self.label}>'

        with self._condition:
            if not self._done:
                return f'<AsyncValue pending: {self.label}>'
            if self._exception is not None:
                return f'<AsyncValue failed: {self.label}>'
            return f'<AsyncValue done: {self.label}>'


class TCPBackend(ChoreographyBackend):
    """Run one party of a choreography over TCP.

    This backend does not fork. Each party should run the same choreography
    program in a separate Python process, passing its local party as `me` and a
    shared address map for all parties.
    """

    def __init__(
        self,
        parties,
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
        self._connect_all()
        return super().__enter__()

    def __exit__(self, exception_type, exception_value, traceback):
        self._close_network()
        super().__exit__(exception_type, exception_value, traceback)
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
            lv.parties.add(party_to)
            return

        if self.party == party_from:
            val = self.unwrap(lv, {party_from})
            self.streams[party_to].put_obj(val)
        elif self.party == party_to:
            val = self.streams[party_from].get_obj()
            object.__setattr__(lv, 'val', val)

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
        return self.addresses[self.parties[party_index]]

    def _validate_addresses(self, addresses):
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


class TCPAsyncBackend(TCPBackend):
    """Run one party over TCP using dataflow futures for sends and local work."""

    def __init__(
        self,
        parties,
        *,
        me: Party,
        addresses: Mapping[Party, tuple[str, int]],
        connect_timeout: float = 10.0,
        max_workers: Optional[int] = None,
    ):
        super().__init__(
            parties,
            me=me,
            addresses=addresses,
            connect_timeout=connect_timeout,
        )
        self.max_workers = max_workers or max(4, len(self.parties) * 4)
        self.executor = None
        self._first_executor = None
        self.write_locks = {}
        self.reader_threads = []

        self._send_counters = defaultdict(int)
        self._send_futures = []
        self._task_futures = set()
        self._task_lock = threading.Lock()

        self._receive_lock = threading.Lock()
        self._pending_receives = {}
        self._receive_futures = []
        self._early_messages = {}
        self._registered_receive_keys = set()
        self._seen_message_keys = set()
        self._closed_remotes = {}
        self._reader_errors = []
        self._closing = False

    def __enter__(self):
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._first_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._connect_all()
        self.write_locks = {
            party: threading.Lock()
            for party in self.streams
        }
        self._start_readers()
        return ChoreographyBackend.__enter__(self)

    def __exit__(self, exception_type, exception_value, traceback):
        try:
            if exception_type is None:
                self._wait_for_send_futures()
                self._wait_for_receive_futures()
                self._raise_reader_errors()
            else:
                self._fail_pending_receives(
                    RuntimeError('TCPAsyncBackend exiting due to an exception')
                )
        finally:
            self._closing = True
            self._fail_pending_receives(RuntimeError('TCPAsyncBackend closed'))
            self._close_network()
            self._join_readers()
            if self.executor is not None:
                self.executor.shutdown(wait=True)
                self.executor = None
            if self._first_executor is not None:
                self._first_executor.shutdown(wait=True)
                self._first_executor = None
            ChoreographyBackend.__exit__(
                self,
                exception_type,
                exception_value,
                traceback,
            )
        return False

    def send(
        self,
        party_from: Party,
        party_to: Party,
        lv: LocatedVal,
        note: Optional[str] = None,
    ) -> None:
        """Schedule a send without blocking on either sender or receiver."""
        assert isinstance(lv, LocatedVal)
        assert isinstance(party_from, Party)
        assert isinstance(party_to, Party)
        assert party_from in lv.parties

        if party_from == party_to:
            lv.parties.add(party_to)
            return

        key = None
        if self.party == party_from or self.party == party_to:
            key = self._next_message_key(party_from, party_to)

        if self.party == party_from:
            send_future = self._submit_now(
                lambda: self._send_envelope(party_from, party_to, key, lv.val),
                f'send {key}',
            )
            with self._task_lock:
                self._send_futures.append(send_future)
        elif self.party == party_to:
            value = self._register_receive(key, party_from)
            object.__setattr__(lv, 'val', value)

        lv.parties.add(party_to)

    def locally(self, f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
        """Create a future local computation without forcing inputs inline."""
        new_args, args_parties = self._get_unforced(args)
        new_kwargs, kwargs_parties = self._get_unforced(kwargs) if kwargs else ({}, None)
        new_parties = _intersect_party_sets(
            [args_parties, kwargs_parties],
            'No participating parties for async local computation',
        )

        if self.party in new_parties:
            output = self._defer(
                lambda: self._call_locally(f, new_args, new_kwargs),
                f'locally {getattr(f, "__name__", repr(f))}',
            )
        else:
            output = None
        return LocatedVal(new_parties.copy(), output)

    def unwrap(self, lv: LocatedVal, parties: Set[Party]) -> Any:
        """Return this process's raw value, forcing futures when necessary."""
        assert isinstance(lv, LocatedVal)
        if isinstance(parties, Party):
            parties = {parties}
        if parties.issubset(lv.parties) and self.party in parties:
            return self._force(lv.val)
        return None

    def first(self, values) -> LocatedVal:
        """Create a future that resolves to the first successful candidate."""
        values, parties = _validate_first_values(values)
        if self.party in parties:
            output = self._defer(
                lambda: self._first_success(values, parties),
                'first',
            )
        else:
            output = None
        return LocatedVal(parties.copy(), output)

    def unlist(self, ls, length):
        assert isinstance(length, int)
        assert isinstance(ls, LocatedVal)

        parties = ls.parties
        if self.party not in parties:
            return [LocatedVal(parties.copy(), None) for _ in range(length)]

        return [
            LocatedVal(
                parties.copy(),
                self._defer(
                    lambda index=index: self._list_item(ls.val, length, index),
                    f'unlist[{index}]',
                ),
            )
            for index in range(length)
        ]

    def untup(self, ls, length):
        assert isinstance(length, int)
        assert isinstance(ls, LocatedVal)

        parties = ls.parties
        if self.party not in parties:
            return tuple(LocatedVal(parties.copy(), None) for _ in range(length))

        return tuple(
            LocatedVal(
                parties.copy(),
                self._defer(
                    lambda index=index: self._tuple_item(ls.val, length, index),
                    f'untup[{index}]',
                ),
            )
            for index in range(length)
        )

    def undict(self, d, keys):
        assert isinstance(d, LocatedVal)

        parties = d.parties
        if self.party not in parties:
            return {key: LocatedVal(parties.copy(), None) for key in keys}

        return {
            key: LocatedVal(
                parties.copy(),
                self._defer(
                    lambda key=key: self._dict_item(d.val, keys, key),
                    f'undict[{key!r}]',
                ),
            )
            for key in keys
        }

    def format_located(self, lv: LocatedVal) -> str:
        return f'{self.unwrap(lv, lv.parties)}@{lv.parties}'

    def compare_located(self, left: LocatedVal, right: Any, op: Callable):
        return self.locally(op, left, right)

    def _next_message_key(self, party_from, party_to):
        edge = (party_from.name, party_to.name)
        sequence = self._send_counters[edge]
        self._send_counters[edge] += 1
        return (party_from.name, party_to.name, sequence)

    def _defer(self, fn, label):
        return AsyncValue(compute=fn, label=label)

    def _submit_now(self, fn, label):
        if self.executor is None:
            raise RuntimeError('TCPAsyncBackend is not running')
        future = self.executor.submit(fn)
        with self._task_lock:
            self._task_futures.add(future)
        future.add_done_callback(self._discard_task_future)
        return future

    def _discard_task_future(self, future):
        with self._task_lock:
            self._task_futures.discard(future)

    def _force(self, value):
        value = self._resolve_async(value)
        if isinstance(value, list):
            return [self._force(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._force(v) for v in value)
        if isinstance(value, dict):
            return {k: self._force(v) for k, v in value.items()}
        return value

    def _resolve_async(self, value):
        while isinstance(value, AsyncValue):
            value = value.result()
        return value

    def _get_unforced(self, value):
        if isinstance(value, LocatedVal):
            return self._unforced_located_value(value), value.parties
        if isinstance(value, tuple):
            vals, parties = self._get_unforced_sequence(value)
            return tuple(vals), parties
        if isinstance(value, list):
            vals, parties = self._get_unforced_sequence(value)
            return vals, parties
        if isinstance(value, dict):
            vals = {}
            party_sets = []
            for key, item in value.items():
                val, parties = self._get_unforced(item)
                vals[key] = val
                party_sets.append(parties)
            if len(party_sets) == 0:
                return vals, None
            return vals, _intersect_party_sets(
                party_sets,
                'No participating parties for async local computation',
            )
        if isinstance(value, (int, float, str, bytes)):
            return value, None
        raise Exception(f'Unsupported value for local computation: {value} : {type(value)}')

    def _call_locally(self, f, args, kwargs):
        return f(*self._force(args), **self._force(kwargs))

    def _first_success(self, values, parties):
        futures = [
            self._submit_first(lambda value=value: self.unwrap(value, parties))
            for value in values
        ]
        pending = set(futures)
        first_exception = None

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    return future.result()
                except BaseException as exc:
                    if first_exception is None:
                        first_exception = exc

        raise first_exception

    def _submit_first(self, fn):
        if self._first_executor is None:
            raise RuntimeError('TCPAsyncBackend is not running')
        return self._first_executor.submit(fn)

    def _get_unforced_sequence(self, value):
        if len(value) == 0:
            return [], None
        vals, party_sets = zip(*[self._get_unforced(item) for item in value])
        parties = _intersect_party_sets(
            party_sets,
            'No participating parties for async local computation',
        )
        return list(vals), parties

    def _unforced_located_value(self, lv):
        if self.party in lv.parties:
            return lv.val
        return None

    def _list_item(self, value, length, index):
        values = self._resolve_async(value)
        assert isinstance(values, list)
        assert len(values) == length
        return self._force(values[index])

    def _tuple_item(self, value, length, index):
        values = self._resolve_async(value)
        assert isinstance(values, tuple)
        assert len(values) == length
        return self._force(values[index])

    def _dict_item(self, value, keys, key):
        values = self._resolve_async(value)
        assert isinstance(values, dict)
        assert set(values.keys()) == set(keys)
        return self._force(values[key])

    def _send_envelope(self, party_from, party_to, key, value):
        payload = self._force(value)
        envelope = {
            'type': _ASYNC_ENVELOPE_TYPE,
            'key': key,
            'src': party_from.name,
            'dest': party_to.name,
            'payload': payload,
        }
        with self.write_locks[party_to]:
            self.streams[party_to].put_obj(envelope)

    def _register_receive(self, key, party_from):
        future = Future()
        payload = None
        has_payload = False
        error = None

        with self._receive_lock:
            if key in self._registered_receive_keys:
                raise RuntimeError(f'Duplicate TCPAsyncBackend receive key: {key}')
            self._registered_receive_keys.add(key)

            if key in self._early_messages:
                payload = self._early_messages.pop(key)
                has_payload = True
            elif party_from in self._closed_remotes:
                error = self._closed_remotes[party_from]
            else:
                self._pending_receives[key] = future
            self._receive_futures.append(future)

        if has_payload:
            future.set_result(payload)
        elif error is not None:
            future.set_exception(error)

        return AsyncValue(future=future, label=f'receive {key}')

    def _start_readers(self):
        for party in self.streams:
            thread = threading.Thread(
                target=self._reader_loop,
                args=(party,),
                daemon=True,
            )
            thread.start()
            self.reader_threads.append(thread)

    def _reader_loop(self, remote_party):
        stream = self.streams[remote_party]
        while not self._closing:
            try:
                envelope = stream.get_obj()
            except Exception as exc:
                if not self._closing:
                    self._mark_remote_closed(remote_party, exc)
                return

            if envelope is None:
                self._mark_remote_closed(
                    remote_party,
                    EOFError(f'TCPAsyncBackend stream closed by {remote_party}'),
                )
                return

            try:
                key, payload = self._validate_envelope(remote_party, envelope)
                self._fulfill_receive(key, payload)
            except Exception as exc:
                self._record_reader_error(remote_party, exc)
                return

    def _validate_envelope(self, remote_party, envelope):
        if not isinstance(envelope, dict):
            raise RuntimeError('Invalid TCPAsyncBackend message envelope')
        if envelope.get('type') != _ASYNC_ENVELOPE_TYPE:
            raise RuntimeError('Unexpected TCPAsyncBackend message type')

        key = envelope.get('key')
        src = envelope.get('src')
        dest = envelope.get('dest')
        if src != remote_party.name:
            raise RuntimeError('TCPAsyncBackend message source mismatch')
        if dest != self.party.name:
            raise RuntimeError('TCPAsyncBackend message destination mismatch')
        if (
            not isinstance(key, tuple)
            or len(key) != 3
            or key[0] != src
            or key[1] != dest
            or not isinstance(key[2], int)
            or key[2] < 0
        ):
            raise RuntimeError('Invalid TCPAsyncBackend message key')
        return key, envelope.get('payload')

    def _fulfill_receive(self, key, payload):
        future = None
        with self._receive_lock:
            if key in self._seen_message_keys:
                raise RuntimeError(f'Duplicate TCPAsyncBackend message key: {key}')
            self._seen_message_keys.add(key)

            future = self._pending_receives.pop(key, None)
            if future is None:
                self._early_messages[key] = payload

        if future is not None:
            future.set_result(payload)

    def _mark_remote_closed(self, remote_party, error):
        futures = []
        with self._receive_lock:
            self._closed_remotes[remote_party] = error
            for key, future in list(self._pending_receives.items()):
                if key[0] == remote_party.name:
                    futures.append(future)
                    del self._pending_receives[key]

        for future in futures:
            if not future.done():
                future.set_exception(error)

    def _record_reader_error(self, remote_party, error):
        with self._receive_lock:
            self._reader_errors.append(error)
        self._mark_remote_closed(remote_party, error)

    def _fail_pending_receives(self, error):
        with self._receive_lock:
            futures = list(self._pending_receives.values())
            self._pending_receives.clear()

        for future in futures:
            if not future.done():
                future.set_exception(error)

    def _wait_for_send_futures(self):
        with self._task_lock:
            send_futures = list(self._send_futures)
        for future in send_futures:
            future.result()

    def _wait_for_receive_futures(self):
        with self._receive_lock:
            receive_futures = list(self._receive_futures)
        for future in receive_futures:
            future.result()

    def _raise_reader_errors(self):
        with self._receive_lock:
            if self._reader_errors:
                raise self._reader_errors[0]

    def _close_network(self):
        for stream in self.streams.values():
            if stream.sock is not None:
                try:
                    stream.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self._join_readers()
        super()._close_network()

    def _join_readers(self):
        for thread in self.reader_threads:
            thread.join(timeout=1.0)
        self.reader_threads = []


class ForkingTCPBackend:
    """Run all parties as forked local processes connected by TCP.

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
        self.parties = _validate_parties(parties)
        self.host = host
        self.base_port = base_port
        self.connect_timeout = connect_timeout
        self.party = None
        self.party_index = None
        self.child_pids = []
        self.is_child = False
        self.backend = None

    def __enter__(self):
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


class ForkingTCPAsyncBackend:
    """Run all parties as forked local processes using TCPAsyncBackend."""

    def __init__(
        self,
        parties,
        host: str = '127.0.0.1',
        base_port: int = 10000,
        connect_timeout: float = 10.0,
        max_workers: Optional[int] = None,
    ):
        self.parties = _validate_parties(parties)
        self.host = host
        self.base_port = base_port
        self.connect_timeout = connect_timeout
        self.max_workers = max_workers
        self.party = None
        self.party_index = None
        self.child_pids = []
        self.is_child = False
        self.backend = None

    def __enter__(self):
        if not hasattr(os, 'fork'):
            raise RuntimeError(
                'ForkingTCPAsyncBackend requires os.fork and a Unix-like platform'
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
        self.backend = TCPAsyncBackend(
            self.parties,
            me=self.party,
            addresses=addresses,
            connect_timeout=self.connect_timeout,
            max_workers=self.max_workers,
        )
        return self.backend.__enter__()

    def __exit__(self, exception_type, exception_value, traceback):
        backend_exit_error = None
        if self.backend is not None:
            try:
                self.backend.__exit__(exception_type, exception_value, traceback)
            except BaseException as exc:
                backend_exit_error = exc

        if self.is_child:
            if backend_exit_error is not None:
                raise backend_exit_error
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

        if backend_exit_error is not None:
            raise backend_exit_error
        if exception_type is None and failures:
            raise RuntimeError(
                f'ForkingTCPAsyncBackend child process failures: {failures}'
            )
        return False
