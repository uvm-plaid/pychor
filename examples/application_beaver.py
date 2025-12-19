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
    def input_p1(cls, val):
        s1, s2 = share(val).untup(2)
        s2.send(p1, p2)
        return SecInt(s1, s2)

    @classmethod
    def input_p2(cls, val):
        s1, s2 = share(val).untup(2)
        s1.send(p2, p1)
        return SecInt(s1, s2)

    def __add__(x, y):
        return SecInt(x.s1 + y.s1,
                      x.s2 + y.s2)

    def __mul__(x, y):
        triple = multiplication_triples.pop()
        r1, r2 = protocol_mult((x.s1, x.s2),
                               (y.s1, y.s2),
                               triple)
        return SecInt(r1, r2)

    def reveal(self):
        self.s1.send(p1, p2)
        self.s2.send(p2, p1)
        return self.s1 + self.s2

if __name__ == '__main__':
    with pychor.LocalBackend():
        # P1 knows the input x, and P2 knows the input y
        x_input = 3@p1
        y_input = 4@p2

        # Create secret shares of the inputs
        x = SecInt.input_p1(x_input)
        y = SecInt.input_p2(y_input)
        print(x)

        for _ in range(20):
            multiplication_triples.append(deal_triple())

        r1 = x + y
        print('x + y:', r1.reveal())

        r2 = x * y
        print('x * y:', r2.reveal())

        r3 = x * y * y
        print('x * y * y:', r3.reveal())
