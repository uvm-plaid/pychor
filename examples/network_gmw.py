import pychor
from dataclasses import dataclass
import urllib.request
import galois
import protocol_ot
import sys

import protocol_gmw

if __name__ == '__main__':
    my_party_name = sys.argv[1]
    p1 = pychor.Party('party1')
    p2 = pychor.Party('party2')

    if my_party_name == 'party1':
        my_party = p1
    else:
        my_party = p2

    addresses = {p1 : ('127.0.0.1', 4545),
                 p2 : ('127.0.0.1', 4546)}

    with pychor.TCPBackend(my_party, addresses):
        protocol_gmw.run_gmw(p1, p2)
