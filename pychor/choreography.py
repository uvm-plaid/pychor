"""Core choreography API for PyChor.

The objects in this module let a program name protocol participants, locate
ordinary Python values at those participants, run local computations, and record
communication between parties through a backend.
"""

from dataclasses import dataclass
from collections import defaultdict
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

    def view(self):
        """Return values sent to this party in the active backend."""
        return cc.views[self]

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
        the transfer locally and makes the destination party an owner of the
        value.
        """
        cc.send(src, dest, self, note)

    def __str__(self):
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

    def unlist(self, ls, length):
        """Un-structure a located list into a list of located values."""
        pass

    def untup(self, ls, length):
        """Un-structure a located tuple into a list of located values."""
        pass

    def undict(self, d, keys):
        """Un-structure a located dict into a dict of located values."""
        pass

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
    stores sent values in per-party views and records communication in Mermaid
    sequence diagram syntax.
    """

    def __init__(self):
        self.views = defaultdict(list)

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
        """Record a local send and add the destination to the value owners."""
        assert isinstance(lv, LocatedVal)
        assert isinstance(party_from, Party)
        assert isinstance(party_to, Party)
        assert party_from in lv.parties

        val = self.unwrap(lv, {party_from})
        self.views[party_to].append(val)
        lv.parties.add(party_to)

        val_str = str(val)
        if len(val_str) > 10:
            val_str = val_str[:10] + '...'

        if note is not None:
            val_str = f'{val_str} ({note})'

        self.emit_to_sequence(f'{party_from.name} ->> {party_to.name} : {val_str}')

    def locally(self, f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
        """Evaluate `f` on the raw values of co-located arguments."""
        new_args, new_parties = get_val(args)
        #new_kwargs, new_parties_k = get_val(kwargs)
        output = f(*new_args)#, **new_kwargs)

        return LocatedVal(new_parties.copy(), output)

    def unwrap(self, lv: LocatedVal, p: Set[Party]) -> Any:
        """Return a raw value when all requested parties own it."""
        assert isinstance(lv, LocatedVal)
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
        assert d.val.keys() == keys
        p = d.party

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


def get_val(lv):
    if isinstance(lv, LocatedVal):
        return cc.unwrap(lv, lv.parties), lv.parties
    elif isinstance(lv, (tuple, list)):
        vals, parties_ls = zip(*[get_val(x) for x in lv])
        parties_setlist = [p for p in parties_ls if p is not None]
        assert len(parties_setlist) > 0, f'No party information for {lv}'
        parties = set.intersection(*parties_setlist)
        assert len(parties) > 0, f'No participating parties for {lv}'
        return vals, parties
    # elif isinstance(lv, (dict)):
    #     return {get_val(k, party): get_val(v, party) for k, v in lv.items()}
    elif isinstance(lv, (int, float, str)):
        return lv, None
    # else:
    #     return lv
    else:
        raise Exception(f'Unsupported value for local computation: {lv} : {type(lv)}')

def constant(party: Party, v: Any) -> LocatedVal:
    """Create a located value owned by `party`."""
    assert not isinstance(v, LocatedVal)
    return LocatedVal({party}, v)

def locally(f: Callable, *args: Any) -> LocatedVal:
    """Run `f` as a local computation in the active backend."""
    return cc.locally(f, *args)

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
