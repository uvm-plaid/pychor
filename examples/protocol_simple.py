import pychor

p1 = pychor.Party('party1')
p2 = pychor.Party('party2')

with pychor.LocalBackend(emit_sequence=True):
    x = 5@p1
    print('x', x)
    x.send(src=p1, dest=p2)
    print('x', x)
    z = 6@p2
    y = pychor.locally(lambda x, z: x+z, x, z)
    print('y', y)
    y.send(src=p2, dest=p1)
    print('y', y)
