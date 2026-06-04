"""Core choreography API for PyChor.

The objects in this module let a program name protocol participants, locate
ordinary Python values at those participants, run local computations, and record
communication between parties through a backend.
"""

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, Set
import socket
import time
from functools import wraps

from . import object_stream

cc = None

@dataclass(frozen=True)
class Party:
    """A named participant in a choreography.

    `Party` objects are used as ownership labels for located values. The
    expression `value @ party` locates an ordinary Python value at that party
    when a choreography backend is active.

    Args:
        name: Human-readable party name used in representations and sequence
            diagrams.
    """

    name: str

    def constant(self, v: Any) -> Any:
        """Locate a value or function at this party.

        Ordinary values become `LocatedVal` objects owned by this party.
        Callables become wrappers that execute the callable locally through the
        active backend.
        """
        assert cc is not None, 'No PyChor backend is running'

        if callable(v):
            def wrapped(*args, **kwargs):
                return cc.locally(v, *args, **kwargs)
            return wrapped
        elif isinstance(v, int):
            return constant(self, v)
        elif isinstance(v, float):
            return constant(self, v)
        elif isinstance(v, list):
            return constant(self, v)
        elif isinstance(v, bytes):
            return constant(self, v)
        elif isinstance(v, str):
            return constant(self, v)
        else:
            return constant(self, v)
        # else:
        #     raise Exception(f'Non-locatable value: {v}')

    def __rmatmul__(self, v):
        """Implement `value @ party` as shorthand for `party.constant(value)`."""
        return self.constant(v)

    def __repr__(self):
        return self.name

@dataclass(frozen=True)
class LocatedVal:
    """A Python value together with the parties that can currently observe it.

    Located values are produced by locating constants, sending values between
    parties, and running local computations. Arithmetic operators on located
    values run through the active backend and produce new located values.

    Args:
        parties: Parties that currently know the underlying value.
        val: The underlying Python value in the active backend.
        note: Optional annotation for protocol explanations or diagrams.
    """

    parties: Set[Party]
    val: Any
    note: Optional[str] = None

    def __post_init__(self):
        assert len(self.parties) > 0

    def send(self, src: Party, dest: Party, note: Optional[str] = None) -> None:
        """Send this located value from `src` to `dest`.

        The active backend performs the communication. `LocalBackend` records
        the transfer in its sequence diagram and makes the destination party
        an owner of the value.
        """
        cc.send(src, dest, self, note)

    def __str__(self):
        if cc is not None:
            return cc.format_located(self)
        return f'{self.val}@{self.parties}'

    def __neg__(self):
        return cc.locally(lambda x: -x, self)

    def __mod__(self, other):
        return cc.locally(lambda x, y: x % y, self, other)

    def __add__(self, other):
        return cc.locally(lambda x, y: x + y, self, other)
    __radd__ = __add__

    def __sub__(self, other):
        return cc.locally(lambda x, y: x - y, self, other)
    def __rsub__(self, other):
        return cc.locally(lambda x, y: y - x, self, other)

    def __mul__(self, other):
        return cc.locally(lambda x, y: x * y, self, other)
    __rmul__ = __mul__

    def __truediv__(self, other):
        return cc.locally(lambda x, y: x / y, self, other)
    def __rtruediv__(self, other):
        return cc.locally(lambda x, y: y / x, self, other)

    def __eq__(self, other):
        if cc is not None:
            return cc.compare_located(self, other, lambda x, y: x == y)
        if not isinstance(other, LocatedVal):
            return False
        return (
            self.parties == other.parties
            and self.val == other.val
            and self.note == other.note
        )

    def __ne__(self, other):
        if cc is not None:
            return cc.compare_located(self, other, lambda x, y: x != y)
        return not self.__eq__(other)

    __repr__ = __str__

    def unlist(self, length):
        """Un-structure a located list into a list of located values."""
        return cc.unlist(self, length)

    def untup(self, length):
        """Un-structure a located tuple into a list of located values."""
        return cc.untup(self, length)

    def undict(self, keys):
        """Un-structure a located dict into a dict of located values."""
        return cc.undict(self, keys)

    def only(self, parties):
        """Limit a located value to a subset of its owners."""
        if isinstance(parties, Party):
            assert parties in self.parties
            return LocatedVal({parties}, self.val, self.note)
        elif isinstance(parties, (list, set)):
            assert parties in self.parties
            return LocatedVal(set(parties), self.val, self.note)
        else:
            raise Exception('failure')

class ChoreographyBackend:
    """Base context manager for choreography backends.

    Entering a backend context makes it the active backend for `Party`,
    `LocatedVal`, `locally`, and `local_function` operations. Subclasses provide
    the actual execution and communication semantics.
    """

    def __init__(self, parties):
        self.parties = _validate_parties(parties)
        self.party_set = set(self.parties)

    def constant(self, party: Party, v: Any) -> LocatedVal:
        """Create a located value owned by `party`."""
        assert not isinstance(v, LocatedVal)
        if party not in self.party_set:
            raise ValueError(f'Party {party} is not part of this backend')
        return LocatedVal({party}, v)

    def send(
        self,
        party_from: Party,
        party_to: Party,
        lv: LocatedVal,
        note: Optional[str] = None,
    ) -> None:
        """Send a located value from one party to another."""
        pass

    def locally(self, f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
        """Compute a function locally using located arguments."""
        pass

    def unwrap(self, lv: LocatedVal, parties: Set[Party]) -> Any:
        """Return the raw value when all requested parties can observe it."""
        pass

    def first(self, values) -> LocatedVal:
        """Return the first located value under this backend's execution order."""
        values, parties = _validate_first_values(values)
        return LocatedVal(parties.copy(), self.unwrap(values[0], parties))

    def unlist(self, ls, length):
        """Un-structure a located list into a list of located values."""
        pass

    def untup(self, ls, length):
        """Un-structure a located tuple into a list of located values."""
        pass

    def undict(self, d, keys):
        """Un-structure a located dict into a dict of located values."""
        pass

    def format_located(self, lv: LocatedVal) -> str:
        """Format a located value for display."""
        return f'{lv.val}@{lv.parties}'

    def compare_located(self, left: LocatedVal, right: Any, op: Callable):
        """Compare located values using the backend's equality semantics."""
        if not isinstance(right, LocatedVal):
            sentinel = object()
            return False if op(sentinel, sentinel) else True
        return op(
            (left.parties, left.val, left.note),
            (right.parties, right.val, right.note),
        )

    def __enter__(self):
        global cc
        cc = self
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        global cc
        cc = None

class LocalBackend(ChoreographyBackend):
    """Run a choreography in a single local Python process.

    `LocalBackend` is useful for tutorials, tests, and protocol sketches. It
    records communication in Mermaid sequence diagram syntax.
    """

    def __init__(self, parties):
        super().__init__(parties)

        # Emit sequence diagram?
        self.uml = ""
        self.emit_to_sequence('sequenceDiagram')

    def send(
        self,
        party_from: Party,
        party_to: Party,
        lv: LocatedVal,
        note: Optional[str] = None,
    ) -> None:
        """Record a local send in the diagram and add the destination owner."""
        assert isinstance(lv, LocatedVal)
        assert isinstance(party_from, Party)
        assert isinstance(party_to, Party)
        assert party_from in lv.parties

        val = self.unwrap(lv, {party_from})
        lv.parties.add(party_to)

        val_str = str(val)
        if len(val_str) > 10:
            val_str = val_str[:10] + '...'

        if note is not None:
            val_str = f'{val_str} ({note})'

        self.emit_to_sequence(f'{party_from.name} ->> {party_to.name} : {val_str}')

    def locally(self, f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
        """Evaluate `f` on the raw values of co-located arguments."""
        new_args, args_parties = get_val(args)
        new_kwargs, kwargs_parties = get_val(kwargs) if kwargs else ({}, None)
        new_parties = _intersect_party_sets(
            [args_parties, kwargs_parties],
            f'No participating parties for {args}',
        )
        output = f(*new_args, **new_kwargs)

        return LocatedVal(new_parties.copy(), output)

    def unwrap(self, lv: LocatedVal, p: Set[Party]) -> Any:
        """Return a raw value when all requested parties own it."""
        assert isinstance(lv, LocatedVal)
        if isinstance(p, Party):
            p = {p}
        if p.issubset(lv.parties):
            return lv.val
        else:
            return None

    def unlist(self, ls, length):
        assert isinstance(ls, LocatedVal)
        assert isinstance(ls.val, list)
        assert len(ls.val) == length
        p = ls.parties

        return [LocatedVal(p.copy(), x) for x in ls.val]

    def untup(self, ls, length):
        assert isinstance(ls, LocatedVal)
        assert isinstance(ls.val, tuple)
        assert len(ls.val) == length
        p = ls.parties
        return tuple([LocatedVal(p.copy(), x) for x in ls.val])

    def undict(self, d, keys):
        assert isinstance(d, LocatedVal)
        assert isinstance(d.val, dict)
        assert set(d.val.keys()) == set(keys)
        p = d.parties

        return {k: LocatedVal(p.copy(), x) for k, x in d.val.items()}

    def emit_to_sequence(self, string):
        """Append a line to the backend's Mermaid sequence diagram."""
        self.uml = self.uml + string + '\n'

    def print_sequence_diagram(self):
        """Print the backend's recorded Mermaid sequence diagram."""
        print('==================================================')
        print('UML Sequence Diagram:')
        print(self.uml)
        print('==================================================')


def _validate_parties(parties):
    try:
        party_list = tuple(parties)
    except TypeError as exc:
        raise TypeError('parties must be an iterable of Party objects') from exc

    if len(party_list) == 0:
        raise ValueError('At least one party is required')
    if not all(isinstance(p, Party) for p in party_list):
        raise TypeError('parties must contain only Party objects')

    party_names = [p.name for p in party_list]
    if len(set(party_names)) != len(party_names):
        raise ValueError('Party names must be unique')

    return party_list


def _intersect_party_sets(party_sets, error_message):
    party_sets = [p for p in party_sets if p is not None]
    assert len(party_sets) > 0, error_message
    parties = set.intersection(*party_sets)
    assert len(parties) > 0, error_message
    return parties


def _validate_first_values(values):
    try:
        value_list = list(values)
    except TypeError as exc:
        raise TypeError('first values must be an iterable of LocatedVal objects') from exc

    if len(value_list) == 0:
        raise ValueError('first requires at least one value')

    if not all(isinstance(value, LocatedVal) for value in value_list):
        raise TypeError('first values must all be LocatedVal objects')

    parties = set.intersection(*[value.parties for value in value_list])
    if len(parties) == 0:
        raise ValueError('first values must have at least one party in common')

    return value_list, parties


def get_val(lv):
    if isinstance(lv, LocatedVal):
        return cc.unwrap(lv, lv.parties), lv.parties
    elif isinstance(lv, (tuple, list)):
        vals, parties_ls = zip(*[get_val(x) for x in lv])
        parties = _intersect_party_sets(
            parties_ls,
            f'No participating parties for {lv}',
        )
        return vals, parties
    elif isinstance(lv, dict):
        vals = {}
        parties_ls = []
        for k, v in lv.items():
            val, parties = get_val(v)
            vals[k] = val
            parties_ls.append(parties)
        if len(parties_ls) == 0:
            return vals, None
        parties = _intersect_party_sets(
            parties_ls,
            f'No participating parties for {lv}',
        )
        return vals, parties
    elif isinstance(lv, (int, float, str, bytes)):
        return lv, None
    else:
        raise Exception(f'Unsupported value for local computation: {lv} : {type(lv)}')

def constant(party: Party, v: Any) -> LocatedVal:
    """Create a located value owned by `party`."""
    assert cc is not None, 'No PyChor backend is running'
    return cc.constant(party, v)

def locally(f: Callable, *args: Any) -> LocatedVal:
    """Run `f` as a local computation in the active backend."""
    return cc.locally(f, *args)

def first(values) -> LocatedVal:
    """Return a located value that resolves to the first successful candidate."""
    assert cc is not None, 'No PyChor backend is running'
    return cc.first(values)

def local_function(func: Callable) -> Callable:
    """Decorate a Python function so it becomes backend-aware.

    Outside a backend context, the decorated function behaves like the original
    function. Inside a backend context, it executes through `locally` and returns
    a located value.
    """
    @wraps(func)
    def localfn(*args):
        if cc is None:
            return func(*args)
        else:
            return cc.locally(func, *args)
    return localfn
