import pychor
from dataclasses import dataclass
import urllib.request
import galois

GF = galois.GF(2**31-1)
#GF = galois.GF(19)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')
dealer = pychor.Party('dealer')
#GF = galois.GF(17)

@pychor.local_function
def share(x):
    s1 = GF.Random()
    s2 = GF(x) - s1
    return s1, s2

def deal_shares(x):
    s1, s2 = share(x).untup(2)
    s1.send(dealer, p1)
    s2.send(dealer, p2)
    return s1, s2

def deal_triple():
    # Step 1: generate a, b, c
    a = dealer.constant(GF.Random())
    b = dealer.constant(GF.Random())
    c = a * b

    # Step 2: secret share a, b, c
    a1, a2 = deal_shares(a)
    b1, b2 = deal_shares(b)
    c1, c2 = deal_shares(c)
    return (a1, a2), (b1, b2), (c1, c2)

def protocol_mult(x, y, triple):
    x1, x2 = x
    y1, y2 = y
    (a1, a2), (b1, b2), (c1, c2) = triple

    # Step 1. P1 computes d_1 = x_1 - a_1 and sends the result to P2
    d1 = x1 - a1
    d1.send(p1, p2)

    # Step 2. P2 computes d_2 = x_2 - a_2 and sends the result to P1
    d2 = x2 - a2
    d2.send(p2, p1)

    # Step 3: P1 and P2 both compute $d = d_1 + d_2 = x - a$
    d = d1 + d2

    # Step 4. P1 computes e_1 = y_1 - b_1 and sends the result to P2
    e1 = y1 - b1
    e1.send(p1, p2)

    # Step 5. P2 computes e_2 = y_2 - b_2 and sends the result to P1
    e2 = y2 - b2
    e2.send(p2, p1)

    # Step 6. P1 and P2 both compute $e = e_1 + e_2 = y - b$
    e = e1 + e2

    # Step 7. P1 computes r_1 = d*e + d*b_1 + e*a_1 + c_1
    r_1 = d * e + d * b1 + e * a1 + c1

    # Step 8. P2 computes r_2 = 0 + d*b_2 + e*a_2 + c_2
    r_2 = d * b2 + e * a2 + c2

    return r_1, r_2

if __name__ == '__main__':
    with pychor.LocalBackend():
        # P1 knows the input x, and P2 knows the input y
        x_input = 3@p1
        y_input = 4@p2

        # Create secret shares of the inputs
        x1, x2 = share(x_input).untup(2)
        y1, y2 = share(y_input).untup(2)
        x2.send(p1, p2)
        y1.send(p2, p1)

        # Generate a multiplication triple
        triple = deal_triple()

        # Perform the multiplication
        r1, r2 = protocol_mult((x1, x2), (y1, y2), triple)

        # Broadcast results and print the product
        r1.send(p1, p2)
        r2.send(p2, p1)
        print('Product:', r1 + r2)
