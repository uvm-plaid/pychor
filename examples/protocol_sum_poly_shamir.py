"""The same n-party sum, but over Shamir shares instead of additive ones.

Shamir sharing places each secret on a random polynomial and gives each party
one evaluation point. Addition is still free -- summing shares point-by-point
gives shares of the sum -- so the protocol shape is identical to the additive
version in protocol_sum_poly.py. The difference is reconstruction, which
interpolates the polynomial rather than simply adding the shares up.
"""

import pychor
import shamir
from example_backend import backend, check

def add(a, b):
    return shamir.add(a, b)

def gen_shares(secret, n):
    return shamir.share(secret, n, n)

def sum_shares(shares):
    return shamir.sum(shares)

def sum_protocol(parties, inputs):
    # Round 1: secret sharing
    received_shares = {p: [] for p in parties}

    for p in parties:
        shares = (gen_shares@p)(inputs[p], len(parties)).unlist(len(parties))
        for r, s in zip(parties, shares):
            s.send(p, r, note='input share')
            received_shares[r].append(s.only(r))

    # Round 2: sum and broadcast
    received_totals = {p: [] for p in parties}

    for p in parties:
        total = (sum_shares@p)(received_shares[p])
        for r in parties:
            total.send(p, r, note='subtotal')
            received_totals[r].append(total.only(r))

    # Round 3: Add results
    totals = {}
    for p in parties:
        totals[p] = (shamir.reconstruct@p)(received_totals[p])

    return totals

def main():
    parties = [pychor.Party(f'p{i}') for i in range(1, 6)]

    with backend(parties=parties) as b:
        inputs = {p: pychor.constant(p, i) for i, p in enumerate(parties)}

        result = sum_protocol(parties, inputs)
        print('Results:', result)

        # Inputs are 0 through 4.
        for p in parties:
            check(result[p], 0 + 1 + 2 + 3 + 4, f'total at {p}')
        return result


if __name__ == '__main__':
    main()
