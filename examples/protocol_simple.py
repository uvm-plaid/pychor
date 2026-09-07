"""The smallest complete choreography: locate, send, compute, send back.

Start here. Nothing cryptographic happens -- the point is to watch the party set
attached to each value change as the protocol runs.
"""

import pychor
from example_backend import backend, check

p1 = pychor.Party('party1')
p2 = pychor.Party('party2')


def main():
    with backend(parties=[p1, p2]):
        # 5 is located at party1, so only party1 can compute with it.
        x = 5@p1
        print('x', x)
        check(x, 5, 'x at party1')

        # After the send, both parties know x.
        x.send(src=p1, dest=p2)
        print('x', x)
        check(x, 5, 'x after send')

        # z is party2's alone, so the sum can only be computed at party2 --
        # which is where PyChor puts it, without being told.
        z = 6@p2
        y = pychor.locally(lambda x, z: x+z, x, z)
        print('y', y)
        check(y, 11, 'y at party2')

        y.send(src=p2, dest=p1)
        print('y', y)
        check(y, 11, 'y after send')
        return y


if __name__ == '__main__':
    main()
