"""`SecInt`: a secret-shared integer that behaves like a Python number.

This is the pattern worth copying for anything larger than a single protocol.
`SecInt` wraps a pair of additive shares and implements `__add__` and `__mul__`,
so application code can be written as ordinary arithmetic while every operation
underneath is a multi-party computation. Addition is free; multiplication runs
the Beaver protocol from protocol_beaver.py and consumes one pre-generated
triple.
"""

from dataclasses import dataclass
import galois

from protocol_beaver import *
from example_backend import backend, check

# Beaver multiplication consumes one triple per `*`, drawn from this pool.
multiplication_triples = []

@dataclass
class SecInt:
    s1: galois.GF
    s2: galois.GF

    @classmethod
    def input(cls, val):
        """Secret share an input: p1 holds s1, and p2 holds s2"""
        s1, s2 = share(val).untup(2)
        if p1 in val.parties:
            s2.send(p1, p2)
            return SecInt(s1, s2)
        else:
            s1.send(p2, p1)
            return SecInt(s1, s2)

    def __add__(x, y):
        """Add two SecInt objects using local addition of shares"""
        return SecInt(x.s1 + y.s1,
                      x.s2 + y.s2)

    def __mul__(x, y):
        """Multiply two SecInt objects using a triple"""
        triple = multiplication_triples.pop()
        r1, r2 = protocol_mult((x.s1, x.s2),
                               (y.s1, y.s2),
                               triple)
        return SecInt(r1, r2)

    def reveal(self):
        """Reveal the secret value by broadcast and reconstruction"""
        self.s1.send(p1, p2)
        self.s2.send(p2, p1)
        return self.s1 + self.s2

def main():
    with backend(parties=[p1, p2, dealer]):
        # P1 knows the input x, and P2 knows the input y
        a, b = 3, 4
        x_input = a@p1
        y_input = b@p2

        # Create secret shares of the inputs
        x = SecInt.input(x_input)
        y = SecInt.input(y_input)
        print(x)

        multiplication_triples.clear()
        for _ in range(20):
            multiplication_triples.append(deal_triple())

        r1 = x + y
        print('x + y:', r1.reveal())
        check(r1.reveal(), a + b, 'x + y')

        r2 = x * y
        print('x * y:', r2.reveal())
        check(r2.reveal(), a * b, 'x * y')

        r3 = x * y * y
        print('x * y * y:', r3.reveal())
        check(r3.reveal(), a * b * b, 'x * y * y')


if __name__ == '__main__':
    main()
