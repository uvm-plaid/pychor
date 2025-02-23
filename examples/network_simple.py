import pychor
import sys

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
    x = 5@p1
    print(x)
    xp = x >> p2
    print(xp)
    y = ((lambda x: x+1)@p2)(xp)
    print(y)
    yp = y >> p1
    print(yp)

    print(5@p1)
