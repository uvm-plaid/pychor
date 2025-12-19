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

    def __sub__(self, other):
        return cc.locally(lambda x, y: x - y, self, other)

    def __mul__(self, other):
        return cc.locally(lambda x, y: x * y, self, other)

    def __truediv__(self, other):
        return cc.locally(lambda x, y: x / y, self, other)

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
    def __init__(self, emit_sequence = False):
        self.views = defaultdict(list)

        # Emit sequence diagram?
        self.emit_sequence = emit_sequence

    def send(self, party_from, party_to, lv, note=None):
        assert isinstance(lv, LocatedVal)
        assert isinstance(party_from, Party)
        assert isinstance(party_to, Party)
        assert party_from in lv.parties

        val = self.unwrap(lv, {party_from})
        #self.views[party_to].append(val)
        lv.parties.add(party_to)

        val_str = str(val)
        if len(val_str) > 10:
            val_str = val_str[:10] + '...'

        if note is not None:
            val_str = f'{note} ({val_str})'

        self.emit_to_sequence(f'{party_from.name} ->> {party_to.name} : {val_str}')

    def locally(self, f, *args, **kwargs):
        #print('local', f, args)
        #assert isinstance(parties, set)

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
        if self.emit_sequence:
            # self.uml_file.write(string + '\n')
            self.uml = self.uml + string + '\n'

    def __enter__(self):
        v = super().__enter__()
        if self.emit_sequence:
            # self.uml_file = open('choreography_sequence.uml', 'w')
            self.uml = ""
            # self.emit_to_sequence('@startuml')
            self.emit_to_sequence('sequenceDiagram')
        return v

    def __exit__(self, exception_type, exception_value, traceback):
        super().__exit__(exception_type, exception_value, traceback)
        # if self.emit_sequence:
        #     self.emit_to_sequence('@enduml')
        #     self.uml_file.close()
        if self.emit_sequence:
            print('==================================================')
            print('UML Sequence Diagram:')
            print(self.uml)
            print('==================================================')


class TCPBackend(ChoreographyBackend):
    def __init__(self, my_party, party_addresses):
        self.views = defaultdict(list)
        self.party = my_party
        self.party_addresses = party_addresses
        self.streams = {}
        my_address, my_port = self.party_addresses[self.party]

        # Create my server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind the socket to a specific address and port
        server_socket.bind(('0.0.0.0', my_port))

        # Enable the server to accept connections
        server_socket.listen(5)
        print(f"Server listening on port {my_port}")

        for p1 in self.party_addresses:
            for p2 in self.party_addresses:
                if p1 == self.party and p2 != p1:
                    # I (p1) connect to p2
                    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    while client_socket.connect_ex(party_addresses[p2]) != 0:
                        time.sleep(1)
                    print(f'Connected to party {p2}')
                    self.streams[p2] = object_stream.ObjectStream(client_socket)
                elif p2 == self.party and p2 != p1:
                    # I (p2) accept connection from p1
                    client_socket, addr = server_socket.accept()
                    print(f'Received connection from party {p1} at {addr}')
                    self.streams[p1] = object_stream.ObjectStream(client_socket)
                else:
                    # Nothing for me to do
                    pass


    def send(self, party_to, lv):
        assert isinstance(lv, LocatedVal)
        assert isinstance(party_to, Party)

        party_from = lv.party
        if party_to == party_from:
            return lv
        elif party_from == self.party: # I need to send
            val = self.unwrap(lv, party_from)
            self.streams[party_to].put_obj(val)
            return LocatedVal(party_to, None)
        elif party_to == self.party:   # I need to receive
            val = self.streams[party_from].get_obj()
            return LocatedVal(party_to, val)
        elif party_from != self.party:
            return LocatedVal(party_to, None)
        else:
            raise Exception('unexpected failure!')

    def locally(self, party, f, *args, **kwargs):
        assert isinstance(party, Party)

        if party == self.party:
            new_args = [get_val(lv, party) for lv in args]
            new_kwargs = {x: get_val(lv, party) for x, lv in kwargs}
            output = f(*new_args, **new_kwargs)
            return LocatedVal(party, output)
        else:
            return LocatedVal(party, None)

    def unwrap(self, lv, p):
        assert isinstance(lv, LocatedVal)
        if p == lv.party:
            return lv.val
        else:
            return None

    def untup(self, ls, length):
        assert isinstance(length, int)
        assert isinstance(ls, LocatedVal)

        p = ls.party
        if cc.party == p:
            assert len(ls.val) == length
            return tuple([LocatedVal(p, x) for x in ls.val])
        else:
            return tuple([LocatedVal(p, None) for _ in range(length)])

# def get_val(lv, party):
#     if isinstance(lv, LocatedVal):
#         return cc.unwrap(lv, party)
#     elif isinstance(lv, (tuple, list)):
#         return [get_val(x, party) for x in lv]
#     elif isinstance(lv, (dict)):
#         return {get_val(k, party): get_val(v, party) for k, v in lv.items()}
#     elif isinstance(lv, (int, float, str)):
#         return lv
#     else:
#         return lv
#     # else:
#     #     raise Exception(f'Unsupported value for local computation: {lv} : {type(lv)}')

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
    #return cc.locally({party}, lambda x: x, v)

def locally(f, *args):
    return cc.locally(f, *args)

def local_function(func):
    @wraps(func)
    def localfn(*args):
        return cc.locally(func, *args)
    return localfn
