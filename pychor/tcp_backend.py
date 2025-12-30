# WIP: has not been updated for multiply-located values

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
