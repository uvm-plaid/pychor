"""Core choreography API for PyChor.

The objects in this module let a program name protocol participants, locate
ordinary Python values at those participants, run local computations, and record
communication between parties through a backend.

A choreography is written once, as a single global program, and executed by a
*backend*. `SimulationBackend` (defined here) runs the whole choreography in
one process, which is convenient for design, teaching, and testing. The
backends in
`pychor.tcp_backend` run one party per process over a network. Because the
choreography itself never mentions a backend, the same protocol code runs
unchanged under all of them.

Exactly one backend is active at a time. Entering a backend's `with` block
installs it as the active backend for every operation in this module; leaving the
block uninstalls it, and located values do not outlive the block.
"""

from dataclasses import dataclass
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, Iterable, Optional, Set, Union

__all__ = [
    'Party',
    'LocatedVal',
    'ChoreographyBackend',
    'SimulationBackend',
    'constant',
    'locally',
    'local_function',
    'get_val',
]

# The active backend, installed by ChoreographyBackend.__enter__ and cleared by
# ChoreographyBackend.__exit__. Every operation in this module dispatches
# through it, which is what makes a choreography backend-agnostic.
cc = None

@dataclass(frozen=True)
class Party:
    """A named participant in a choreography.

    `Party` objects are used as ownership labels for located values. The
    expression `value @ party` locates an ordinary Python value at that party
    when a choreography backend is active.

    Parties are frozen dataclasses, so they are hashable and compare by name,
    and the same `Party` object can be shared freely across a program. The
    *order* of the party list passed to a backend is significant for the TCP
    backends: it fixes the connection order and, for `ForkingTCPBackend`, the
    port assignment.

    Args:
        name: Human-readable party name used in representations and sequence
            diagrams.

    Example:
        ```python
        alice = pychor.Party("alice")
        bob = pychor.Party("bob")

        with pychor.SimulationBackend(parties=[alice, bob]):
            x = 5 @ alice
        ```
    """

    name: str

    def constant(self, v: Any) -> Any:
        """Locate a value or function at this party.

        Ordinary values become `LocatedVal` objects owned by this party.
        Callables become wrappers that execute the callable locally through the
        active backend, so `(lambda x: x + 1) @ alice` is a function that runs
        at `alice`.

        Args:
            v: The value to locate, or a callable to run at this party.

        Returns:
            A `LocatedVal` owned by this party, or — when `v` is callable — a
            wrapper that runs `v` as a local computation.

        Raises:
            AssertionError: If no backend is currently active.
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

    def view(self) -> list:
        """Return the values this party has received in the active backend.

        A party's *view* is the ordered list of message payloads delivered to it
        by `LocatedVal.send`, and it is the audit trail that simulation-based
        security arguments inspect: a protocol is private with respect to a
        party if that party's view can be reproduced by a simulator that never
        sees the honest inputs. `examples/protocol_sum.py` compares protocol and
        simulator views statistically using this method.

        Each backend context starts with empty views, so a program that samples
        views over many runs must re-enter the backend for each run.

        Returns:
            The list of values received by this party so far. Under a TCP
            backend, only the calling process's own party has a populated view.

        Raises:
            AttributeError: If no backend is currently active.
        """
        return cc.views[self]

@dataclass(frozen=True)
class LocatedVal:
    """A Python value together with the parties that can currently observe it.

    Located values are produced by locating constants, sending values between
    parties, and running local computations. A located value is the unit of
    ownership in a choreography: `parties` records who knows the value, and the
    backend refuses to compute with a value at a party that does not own it.

    Ownership *grows* when a value is sent — `send` adds the destination to
    `parties` — and is *narrowed* with `only`.

    Under `SimulationBackend`, `val` always holds the real value because a
    single process plays every party. Under the TCP backends, `val` holds the
    real value only in the processes whose party appears in `parties`, and is
    `None` everywhere else; see `pychor.tcp_backend` and the Concepts page of the
    documentation.

    Args:
        parties: Parties that currently know the underlying value.
        val: The underlying Python value in the active backend.
        note: Optional annotation for protocol explanations or diagrams.

    Operators:
        `+`, `-`, `*`, `/`, `%` and unary `-` are defined on located values and
        are each shorthand for a local computation: `x + y` is equivalent to
        `locally(lambda a, b: a + b, x, y)`, so it runs at the parties that own
        *both* operands and produces a new located value. Reflected forms
        (`__radd__` and friends) are defined too, so a plain Python `int`,
        `float`, `str`, or `bytes` may appear on either side; a plain value
        places no ownership constraint of its own. This is what lets share
        arithmetic read like ordinary Python — see
        `examples/protocol_beaver.py`, where a Beaver multiplication is written
        `r_1 = d * e + d * b1 + e * a1 + c1`.

        Comparisons use dataclass equality, which compares the underlying
        values *and* the owner sets; there is no located boolean type.
    """

    parties: Set[Party]
    val: Any
    note: Optional[str] = None

    def __post_init__(self):
        assert len(self.parties) > 0

    def send(self, src: Party, dest: Party, note: Optional[str] = None) -> None:
        """Send this located value from `src` to `dest`.

        The active backend performs the communication and adds `dest` to this
        value's owner set, so the same `LocatedVal` object is afterwards
        readable at both parties. Sending mutates this value in place rather
        than returning a new one.

        Args:
            src: The sending party, which must already own this value.
            dest: The receiving party.
            note: Optional label for this message. `SimulationBackend` appends
                it to the corresponding edge of the sequence diagram, which is
                useful for explaining what a message carries — see
                `examples/protocol_commit.py`.

        Raises:
            AssertionError: If `src` does not own this value.
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

    def unlist(self, length: int) -> list:
        """Un-structure a located list into a list of located values.

        A local computation that returns a list produces a single located list.
        This splits it into `length` located values, each owned by the same
        parties, so the individual elements can be sent to different places.

        Args:
            length: The expected length of the underlying list.

        Returns:
            A Python list of `length` located values.
        """
        return cc.unlist(self, length)

    def untup(self, length: int) -> tuple:
        """Un-structure a located tuple into a tuple of located values.

        This is the usual way to return several results from one local
        computation, as in `s1, s2 = share(x).untup(2)`.

        Args:
            length: The expected length of the underlying tuple.

        Returns:
            A Python tuple of `length` located values.
        """
        return cc.untup(self, length)

    def undict(self, keys: Iterable) -> dict:
        """Un-structure a located dict into a dict of located values.

        Args:
            keys: The expected keys of the underlying dict.

        Returns:
            A Python dict mapping each key to a located value.
        """
        return cc.undict(self, keys)

    def only(self, parties: Union[Party, Iterable[Party]]) -> 'LocatedVal':
        """Return this value restricted to a subset of its current owners.

        Narrowing ownership is how a choreography says "treat this as *bob's*
        value from here on". It matters because a local computation runs at the
        intersection of its arguments' owners: after `x.send(src=alice,
        dest=bob)`, `x` is owned by both parties, so a computation over `x`
        would run at both. Passing `x.only(bob)` instead pins the computation
        to `bob`.

        This does not communicate anything and does not modify this value; it
        returns a new `LocatedVal` sharing the same underlying value.

        Args:
            parties: A single `Party`, or a collection of parties, all of which
                must already own this value.

        Returns:
            A new located value owned by exactly `parties`.

        Raises:
            AssertionError: If any requested party does not already own this
                value, or if an empty collection is given.
            TypeError: If `parties` is neither a `Party` nor a collection of
                parties.
        """
        if isinstance(parties, Party):
            assert parties in self.parties, \
                f'{parties} does not own this value (owners: {self.parties})'
            return LocatedVal({parties}, self.val, self.note)
        elif isinstance(parties, (list, set, frozenset, tuple)):
            new_parties = set(parties)
            assert len(new_parties) > 0, 'only() requires at least one party'
            assert new_parties <= self.parties, \
                f'{new_parties - self.parties} do not own this value ' \
                f'(owners: {self.parties})'
            return LocatedVal(new_parties, self.val, self.note)
        else:
            raise TypeError(
                f'only() expects a Party or a collection of parties, got {parties!r}'
            )

class ChoreographyBackend:
    """Base context manager for choreography backends.

    Entering a backend context makes it the active backend for `Party`,
    `LocatedVal`, `locally`, and `local_function` operations. Subclasses provide
    the actual execution and communication semantics.

    A backend must implement `constant`, `send`, `locally`, `unwrap`, `unlist`,
    `untup`, and `undict`. The methods defined here are the interface: all but
    `constant` are stubs, and a subclass that leaves one unimplemented will
    silently return `None` from the corresponding operation rather than raise.
    `SimulationBackend` is the reference implementation;
    `pychor.tcp_backend.TCPBackend` shows the same interface implemented across
    processes.

    Subclasses that override `__enter__` or `__exit__` must call
    `super().__enter__()` / `super().__exit__()` so that the active-backend
    global is installed and cleared.

    Attributes:
        parties: The backend's parties, as a tuple, in the order given. Order is
            significant for the TCP backends.
        party_set: The same parties as a set, for membership tests.
        views: Maps each party to the ordered list of values it has received.
            This is the protocol transcript from each party's point of view, and
            it is what a simulation-based security argument compares; see
            `Party.view`. Views start empty in each new backend context.

    Args:
        parties: An iterable of `Party` objects with unique names. At least one
            party is required.
    """

    def __init__(self, parties: Iterable[Party]):
        self.parties = _validate_parties(parties)
        self.party_set = set(self.parties)
        self.views = defaultdict(list)

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
        """Send a located value from one party to another.

        Implementations must add `party_to` to `lv.parties` and record the
        received value in `self.views[party_to]`.
        """
        pass

    def locally(self, f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
        """Compute a function locally using located arguments.

        Implementations must evaluate `f` at the intersection of the owner sets
        of the located arguments, and return a located value owned by exactly
        that intersection.
        """
        pass

    def unwrap(self, lv: LocatedVal, parties: Set[Party]) -> Any:
        """Return the raw value when all requested parties can observe it.

        Implementations return `None` rather than raising when the value is not
        available.
        """
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

class SimulationBackend(ChoreographyBackend):
    """Run a choreography in a single local Python process.

    `SimulationBackend` is useful for tutorials, tests, and protocol sketches.
    One process plays every party, so every located value is genuinely present
    and a choreography always runs to completion quickly, with no network setup.

    The trade-off is that this backend cannot detect a choreography that reads a
    value it does not own: nothing is actually distributed, so an illegal read
    still finds a real value in memory. Run a protocol under
    `pychor.tcp_backend.ForkingTCPBackend` to check that it is genuinely
    executable one-party-per-process.

    In exchange, this backend can observe the whole protocol at once. It records
    each send into `views` and accumulates a **Mermaid** sequence diagram in
    `uml`, which `print_sequence_diagram` prints and which can be pasted
    directly into Mermaid-aware Markdown.

    Attributes:
        uml: The accumulated Mermaid sequence diagram source, beginning with the
            line `sequenceDiagram`.

    Example:
        ```python
        with pychor.SimulationBackend(parties=[alice, bob]) as backend:
            x = 5 @ alice
            x.send(src=alice, dest=bob)
            backend.print_sequence_diagram()
        ```
    """

    def __init__(self, parties: Iterable[Party]):
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
        """Record a local send and add the destination to the value owners.

        The value is appended to the destination party's view and an edge is
        added to the sequence diagram. Values whose string form exceeds ten
        characters are truncated with an ellipsis in the diagram only; the value
        delivered to the destination is never truncated.
        """
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
        """Evaluate `f` on the raw values of co-located arguments.

        The result is owned by the intersection of the owner sets of the located
        arguments. Plain Python scalars among the arguments contribute no
        ownership constraint.

        Raises:
            AssertionError: If the located arguments have no owner in common.
        """
        new_args, args_parties = get_val(args)
        new_kwargs, kwargs_parties = get_val(kwargs) if kwargs else ({}, None)
        new_parties = _intersect_party_sets(
            [args_parties, kwargs_parties],
            f'No participating parties for {args}',
        )
        output = f(*new_args, **new_kwargs)

        return LocatedVal(new_parties.copy(), output)

    def unwrap(self, lv: LocatedVal, p: Set[Party]) -> Any:
        """Return a raw value when all requested parties own it.

        Returns:
            The underlying value, or `None` if any requested party is not an
            owner.
        """
        assert isinstance(lv, LocatedVal)
        if isinstance(p, Party):
            p = {p}
        if p.issubset(lv.parties):
            return lv.val
        else:
            return None

    def unlist(self, ls, length):
        """Split a located list of `length` items into that many located values."""
        assert isinstance(ls, LocatedVal)
        assert isinstance(ls.val, list)
        assert len(ls.val) == length
        p = ls.parties

        return [LocatedVal(p.copy(), x) for x in ls.val]

    def untup(self, ls, length):
        """Split a located tuple of `length` items into that many located values."""
        assert isinstance(ls, LocatedVal)
        assert isinstance(ls.val, tuple)
        assert len(ls.val) == length
        p = ls.parties
        return tuple([LocatedVal(p.copy(), x) for x in ls.val])

    def undict(self, d, keys):
        """Split a located dict into a dict of located values, one per key."""
        assert isinstance(d, LocatedVal)
        assert isinstance(d.val, dict)
        assert set(d.val.keys()) == set(keys)
        p = d.parties

        return {k: LocatedVal(p.copy(), x) for k, x in d.val.items()}

    def emit_to_sequence(self, string: str) -> None:
        """Append a line to the backend's Mermaid sequence diagram.

        Use this to add Mermaid directives of your own — notes, activations, or
        participant declarations — alongside the edges `send` records.

        Args:
            string: One line of Mermaid `sequenceDiagram` source, without a
                trailing newline.
        """
        self.uml = self.uml + string + '\n'

    def print_sequence_diagram(self):
        """Print the Mermaid sequence diagram recorded so far.

        The diagram is also available as `uml` if you would rather write it to a
        file or embed it in Markdown. For the choreography in
        `examples/protocol_simple.py`, this prints:

        ```
        sequenceDiagram
        party1 ->> party2 : 5
        party2 ->> party1 : 11
        ```
        """
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


def get_val(lv: Any) -> tuple:
    """Unwrap located values and determine where a computation may run.

    This is the helper backends use to implement `locally`. It walks an argument
    structure, replaces each `LocatedVal` with its underlying value, and
    intersects the owner sets it encounters to decide which parties can perform
    the computation. Tuples, lists, and dicts are traversed recursively, so a
    local function may take nested structures of located values.

    Plain `int`, `float`, `str`, and `bytes` values pass through with no owner
    set, meaning they place no constraint on where the computation runs; this is
    what allows `x + 1` for a located `x`.

    Args:
        lv: A located value, a plain scalar, or a tuple, list, or dict of those.

    Returns:
        A `(values, parties)` pair, where `values` mirrors the structure of `lv`
        with located values replaced by their contents, and `parties` is the set
        of parties able to run the computation — or `None` if `lv` contained no
        located values at all.

    Raises:
        AssertionError: If the located values have no owner in common.
        Exception: If `lv` contains a value that is neither located, a supported
            scalar, nor a supported container.
    """
    if isinstance(lv, LocatedVal):
        return cc.unwrap(lv, lv.parties), lv.parties
    elif isinstance(lv, (tuple, list)):
        vals, parties_ls = zip(*[get_val(x) for x in lv])
        known = [p for p in parties_ls if p is not None]
        if len(known) == 0:
            return vals, None
        parties = _intersect_party_sets(
            known,
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
        known = [p for p in parties_ls if p is not None]
        if len(known) == 0:
            return vals, None
        parties = _intersect_party_sets(
            known,
            f'No participating parties for {lv}',
        )
        return vals, parties
    elif isinstance(lv, (int, float, str, bytes)):
        return lv, None
    else:
        raise Exception(f'Unsupported value for local computation: {lv} : {type(lv)}')

def constant(party: Party, v: Any) -> LocatedVal:
    """Create a located value owned by `party`.

    `party.constant(v)` and `v @ party` are the usual spellings; this function
    is the explicit form, useful when the party is computed.

    Args:
        party: The owning party, which must belong to the active backend.
        v: The value to locate.

    Returns:
        A `LocatedVal` owned by `party`.

    Raises:
        AssertionError: If no backend is currently active.
        ValueError: If `party` is not part of the active backend.
    """
    assert cc is not None, 'No PyChor backend is running'
    return cc.constant(party, v)

def locally(f: Callable, *args: Any, **kwargs: Any) -> LocatedVal:
    """Run `f` as a local computation in the active backend.

    The computation runs at the parties that own *every* located argument, and
    the result is located at exactly those parties. Plain Python scalars may be
    mixed in freely and place no constraint on where the computation runs.

    Under a TCP backend this call is a no-op in processes whose party is not
    among the owners, and the returned located value carries `None` there.

    Args:
        f: An ordinary Python function.
        *args: Located values, plain scalars, or tuples, lists, and dicts of
            those.
        **kwargs: Keyword arguments, handled the same way as `args`.

    Returns:
        A located value holding `f`'s result, owned by the parties that could
        see all of the located inputs.

    Raises:
        AssertionError: If the located arguments have no owner in common.

    Example:
        ```python
        y = pychor.locally(lambda value: value + 1, x)
        ```
    """
    return cc.locally(f, *args, **kwargs)

def local_function(func: Callable) -> Callable:
    """Decorate a Python function so it becomes backend-aware.

    Outside a backend context, the decorated function behaves like the original
    function, which keeps helpers testable on their own. Inside a backend
    context, calling it runs `locally` and returns a located value, so the same
    definition serves both purposes.

    Args:
        func: The function to make backend-aware.

    Returns:
        A wrapper that dispatches to `locally` whenever a backend is active.

    Example:
        ```python
        @pychor.local_function
        def add_bonus(value, bonus):
            return value + bonus

        with pychor.SimulationBackend(parties=[alice, bob]):
            y = add_bonus(5 @ alice, 2)
        ```
    """
    @wraps(func)
    def localfn(*args, **kwargs):
        if cc is None:
            return func(*args, **kwargs)
        else:
            return cc.locally(func, *args, **kwargs)
    return localfn
