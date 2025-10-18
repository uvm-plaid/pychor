import pychor
from dataclasses import dataclass
import urllib.request
import galois

GF = galois.GF(2**31-1)
#GF = galois.GF(19)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')
dealer = pychor.Party('dealer')


def f_mult(x, y, triple):
    # pattern match on shares
    (a1, a2), (b1, b2), (c1, c2) = triple
    x1, x2 = x
    y1, y2 = y

    # calculate and broadcast d
    d1 = x1 - a1
    d1.send(p1, p2, note='broadcast d1')
    d2 = x2 - a2
    d2.send(p2, p1, note='broadcast d2')
    d = d1 + d2

    # calculate and broadcast e
    e1 = y1 - b1
    e1.send(p1, p2, note='broadcast e1')
    e2 = y2 - b2
    e2.send(p2, p1, note='broadcast e2')
    e = e1 + e2

    # calculate shares of output
    prod1 = d * e + d * b1 + e * a1 + c1
    prod2 = d * b2 + e * a2 + c2

    return prod1, prod2

def gen_shares(x):
    s1 = GF.Random()
    s2 = x - s1
    return s1, s2

def deal_shares(x):
    s1, s2 = (gen_shares@dealer)(x).untup(2)
    s1.send(dealer, p1, note='deal share')
    s2.send(dealer, p2, note='deal share')
    return s1, s2

def gen_triple():
    a = dealer.constant(GF.Random())
    b = dealer.constant(GF.Random())
    c = a * b
    return a, b, c

def deal_triple():
    a, b, c = gen_triple()
    a1, a2 = deal_shares(a)
    b1, b2 = deal_shares(b)
    c1, c2 = deal_shares(c)
    return (a1, a2), (b1, b2), (c1, c2)

def reconstruct(x):
    x1, x2 = x
    x1.send(p1, dealer)
    x2.send(p2, dealer)
    return x1 + x2

if __name__ == '__main__':
    with pychor.LocalBackend(emit_sequence = True):
        x = dealer.constant(GF(3))
        y = dealer.constant(GF(5))

        # deal shares of the input values
        xs = deal_shares(x)
        ys = deal_shares(y)

        # print('x:', reconstruct(xs))
        # print('y:', reconstruct(ys))

        # deal a multiplication triple
        t1 = deal_triple()

        # perform the multiplication
        z = f_mult(xs, ys, t1)

        print('x*y:', reconstruct(z))
