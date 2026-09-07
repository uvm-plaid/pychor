"""Two-party addition on secret-shared values, wrapped in a datatype.

`MPCVal` holds one additive share per party and defines `__add__`, so once two
values are shared the arithmetic over them reads like ordinary Python -- the
`total = total + v1 + v2` loop below is a real multi-party computation. Addition
of additive shares needs no communication at all: each party just adds its own
shares locally. Only `make` and `reveal` send anything.
"""

import pychor
import galois
from dataclasses import dataclass
from typing import Dict
from example_backend import backend, check

GF = galois.GF(2**31-1)
#GF = galois.GF(19)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')

@dataclass
class MPCVal:
    shares: Dict[pychor.Party, GF]

    @classmethod
    def make(cls, val, owner, other):
        s1, s2 = pychor.locally(gen_shares, val).untup(2)
        s2.send(owner, other)
        shares = {owner: s1, other: s2.only(other)}
        return MPCVal(shares)

    def __add__(v1, v2):
        assert v1.shares.keys() == v2.shares.keys()
        new_shares = {p: v1.shares[p] + v2.shares[p] for p in v1.shares.keys()}
        return MPCVal(new_shares)

    def reveal(self, destination):
        total = pychor.locally(GF, 0@destination)
        for p, s in self.shares.items():
            s.send(p, destination)
            total = total + s
        return total

def gen_shares(secret):
    s1 = GF.Random()
    s2 = GF(secret) - s1
    return s1, s2

ROUNDS = 20

def sum_protocol(in1, in2):
    # Secret share each party's input.
    v1 = MPCVal.make(in1, p1, p2)
    v2 = MPCVal.make(in2, p2, p1)
    print(v1, v2)

    # Add values.
    # Note that this looks like a regular Python program!
    total = v1 + v2
    for _ in range(ROUNDS):
        total = total + v1 + v2
    print(total)

    # Reveal results
    total = total.reveal(p1)

    return total


def main():
    with backend(parties=[p1, p2]) as b:
        a, b_ = 5, 3
        in1 = a@p1
        in2 = b_@p2

        result = sum_protocol(in1, in2)
        print('Result:', result)

        # One initial sum plus ROUNDS more, each adding v1 + v2 again.
        check(result, (ROUNDS + 1) * (a + b_), 'total')
        return result


if __name__ == '__main__':
    main()
