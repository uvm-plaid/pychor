from dataclasses import dataclass
from collections import defaultdict
from functools import wraps
from typing import Set
import socket
import time
from functools import wraps

from . import object_stream

cc = None

@dataclass(frozen=True)
class Party:
    name: str

    def constant(self, v):
        if callable(v):
            def wrapped(*args, **kwargs):
                return cc.locally(v, *args, **kwargs)
            return wrapped
        elif isinstance(v, int):
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
        return self.constant(v)

    def __repr__(self):
        return self.name

    def view(self):
        return cc.views[self]

@dataclass(frozen=True)
class LocatedVal:
    parties: Set[str]
    val: any
    note: str = None

    def __post_init__(self):
        assert len(self.parties) > 0

    def send(self, src, dest, note=None):
        cc.send(src, dest, self, note)

    def __str__(self):
        return f'{self.val}@{self.parties}'

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
    def send(self, p: Party, lv: LocatedVal, note: str) -> LocatedVal:
        """Send a located value to party p."""
        pass

    def locally(self, p: Party, f: callable, *args, **kwargs) -> any:
        """Compute a function locally at party p."""
        pass

    def unwrap(self, lv: LocatedVal, p: Party) -> any:
        """Unwrap a located value at party p."""
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
    def __init__(self):
        self.views = defaultdict(list)

        # Emit sequence diagram?
        self.uml = ""
        self.emit_to_sequence('sequenceDiagram')

    def send(self, party_from, party_to, lv, note=None):
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

    def locally(self, f, *args, **kwargs):
        new_args, new_parties = get_val(args)
        #new_kwargs, new_parties_k = get_val(kwargs)
        output = f(*new_args)#, **new_kwargs)

        return LocatedVal(new_parties.copy(), output)

    def unwrap(self, lv, p):
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
        self.uml = self.uml + string + '\n'

    def print_sequence_diagram(self):
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

def constant(party, v):
    assert not isinstance(v, LocatedVal)
    return LocatedVal({party}, v)

def locally(f, *args):
    return cc.locally(f, *args)

def local_function(func):
    @wraps(func)
    def localfn(*args):
        return cc.locally(func, *args)
    return localfn
