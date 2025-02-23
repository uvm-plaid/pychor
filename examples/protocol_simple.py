import pychor

p1 = pychor.Party('party1')
p2 = pychor.Party('party2')

with pychor.LocalBackend(emit_sequence=True):
    x = 5@p1
    print(x)
    xp = x >> p2
    print(xp)
    y = ((lambda x: x+1)@p2)(xp)
    print(y)
    yp = y >> p1
    print(yp)

    print(5@p1)
