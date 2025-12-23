import pychor
from dataclasses import dataclass
import galois

from protocol_beaver import *

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

if __name__ == '__main__':
    with pychor.LocalBackend():
        # P1 knows the input x, and P2 knows the input y
        x_input = 3@p1
        y_input = 4@p2

        # Create secret shares of the inputs
        x = SecInt.input(x_input)
        y = SecInt.input(y_input)
        print(x)

        for _ in range(20):
            multiplication_triples.append(deal_triple())

        r1 = x + y
        print('x + y:', r1.reveal())

        r2 = x * y
        print('x * y:', r2.reveal())

        r3 = x * y * y
        print('x * y * y:', r3.reveal())
