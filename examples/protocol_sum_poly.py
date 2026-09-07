"""An n-party sum using additive secret sharing, in three rounds.

Every party splits its input into one share per party and hands them out, so no
single share reveals anything. Each party then adds up the shares it received
and broadcasts that subtotal. Summing the subtotals gives the total, which every
party learns while nobody's individual input is revealed.
"""

import pychor
import galois
from example_backend import backend, check

GF = galois.GF(2**31-1)

def add(a, b):
    return a + b

def gen_shares(secret, n):
    shares = [GF.Random() for _ in range(n-1)]
    last_share = GF(secret) - sum_shares(shares)
    shares.append(last_share)
    return shares

def sum_shares(shares):
    total = GF(0)
    for s in shares:
        total += s
    return total

def sum_protocol(parties, inputs):
    # Round 1: secret sharing
    generated_shares = {p: (gen_shares@p)(inputs[p], len(parties)).unlist(len(parties))
                        for p in parties}

    received_shares = {p: [] for p in parties}
    for p in parties:
        for r, s in zip(parties, generated_shares[p]):
            s.send(p, r, note='input share')
            received_shares[r].append(s.only(r))

    # Round 2: sum and broadcast
    computed_totals = {p: (sum_shares@p)(received_shares[p]) for p in parties}

    received_totals = {p: [] for p in parties}
    for p in parties:
        for r in parties:
            computed_totals[p].send(p, r, note='subtotal')
            received_totals[r].append(computed_totals[p].only(r))

    # Round 3: Add results
    totals = {p: (sum_shares@p)(received_totals[p]) for p in parties}

    return totals

def main():
    parties = [pychor.Party(f'p{i}') for i in range(1, 6)]

    with backend(parties=parties) as b:
        inputs = {p: pychor.constant(p, i) for i, p in enumerate(parties)}

        result = sum_protocol(parties, inputs)
        print('Result:', result)

        # Inputs are 0 through 4.
        for p in parties:
            check(result[p], 0 + 1 + 2 + 3 + 4, f'total at {p}')
        return result


if __name__ == '__main__':
    main()
