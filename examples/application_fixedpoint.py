"""`SecDec`: secret-shared fixed-point decimals.

Secret sharing works over a finite field, which has no fractions -- so a decimal
is represented as an integer scaled by a power of ten, and the exponent is
tracked alongside the shares. Adding requires equal exponents; multiplying adds
them, so each product is truncated back down to keep the exponent from growing.

application_division.py takes this further and divides, where the exponent
budget becomes the binding constraint.
"""

import pychor
from dataclasses import dataclass
import galois

from protocol_beaver import *
from example_backend import backend, check

# Beaver multiplication consumes one triple per `*`, drawn from this pool.
multiplication_triples = []

@pychor.local_function
def encode_fixpoint(val, power):
    return int(val * 10**power)

@dataclass
class SecDec:
    s1: galois.GF
    s2: galois.GF
    power: int

    @classmethod
    def input_p1(cls, val):
        s1, s2 = share(encode_fixpoint(val, 1)).untup(2)
        s2.send(p1, p2)
        return SecDec(s1, s2, 1)

    @classmethod
    def input_p2(cls, val):
        s1, s2 = share(encode_fixpoint(val, 1)).untup(2)
        s1.send(p2, p1)
        return SecDec(s1, s2, 1)

    def __add__(x, y):
        assert x.power == y.power
        return SecDec(x.s1 + y.s1,
                      x.s2 + y.s2,
                      x.power)

    def __mul__(x, y):
        triple = multiplication_triples.pop()
        r1, r2 = protocol_mult((x.s1, x.s2),
                               (y.s1, y.s2),
                               triple)
        return SecDec(r1, r2, x.power + y.power)

    def reveal(self):
        self.s1.send(p1, p2)
        self.s2.send(p2, p1)
        f = lambda s1, s2: int(s1 + s2) / (10**self.power)
        return pychor.locally(f, self.s1, self.s2)

def main():
    with backend(parties=[p1, p2, dealer]):
        # P1 knows the input x, and P2 knows the input y
        a, b = 3.1, 4.2
        x_input = a@p1
        y_input = b@p2

        # Create secret shares of the inputs
        x = SecDec.input_p1(x_input)
        y = SecDec.input_p2(y_input)

        multiplication_triples.clear()
        for _ in range(20):
            multiplication_triples.append(deal_triple())

        # Both inputs land exactly on the one-decimal-place grid, so the results
        # are exact too -- the tolerance is only there to absorb the float
        # rounding in the expected values on the right-hand side.
        r1 = x + y
        print('x + y:', r1.reveal())
        check(r1.reveal(), a + b, 'x + y', tol=1e-9)

        r2 = x * y
        print('x * y:', r2.reveal())
        check(r2.reveal(), a * b, 'x * y', tol=1e-9)

        r3 = x * y * y
        print('x * y * y:', r3.reveal())
        check(r3.reveal(), a * b * b, 'x * y * y', tol=1e-9)


if __name__ == '__main__':
    main()
