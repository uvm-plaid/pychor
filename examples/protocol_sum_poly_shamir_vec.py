"""A vectorized Shamir sum: one protocol run over a whole vector of secrets.

This is protocol_sum_poly_shamir.py with each party's input widened from a
single value to a vector of `d` of them. The point is that the choreography does
not change: the same three rounds carry `d` times as much data, because the
sharing, addition, and reconstruction all apply element-wise. Batching this way
is how real deployments amortize the cost of a protocol over many values.

The transposes are bookkeeping. `shamir.share` produces one list of shares per
secret, and what each party needs is one list of secrets per share -- so the
d-by-n grid gets flipped before it is handed out.
"""

import pychor
import shamir
from example_backend import backend, check

# Number of secrets each party contributes.
d = 20

def transpose(ls):
    return list(map(list, zip(*ls)))

def add(a_list, b_list):
    return [shamir.add(a, b) for a, b in zip(a_list, b_list)]

def gen_shares(secret, n):
    l = [shamir.share(secret, n, n) for _ in range(d)]
    t = transpose(l)
    return t

def sum_shares(shares_list):
    t = transpose(shares_list)
    return [shamir.sum(shares) for shares in t]

def reconstruct(shares_list):
    t = transpose(shares_list)
    return [shamir.reconstruct(shares) for shares in t]

def sum_protocol(parties, inputs):
    # Round 1: secret sharing
    received_shares = {p: [] for p in parties}

    for p in parties:
        shares = (gen_shares@p)(inputs[p], len(parties)).unlist(len(parties))
        for r, s in zip(parties, shares):
            s.send(p, r, note='input shares')
            received_shares[r].append(s.only(r))

    # Round 2: sum and broadcast
    received_totals = {p: [] for p in parties}

    for p in parties:
        total = (sum_shares@p)(received_shares[p])
        for r in parties:
            total.send(p, r, note='subtotals')
            received_totals[r].append(total.only(r))

    # Round 3: Add results
    totals = {}
    for p in parties:
        totals[p] = (reconstruct@p)(received_totals[p])

    return totals

def main():
    parties = [pychor.Party(f'p{i}') for i in range(1, 6)]

    with backend(parties=parties) as b:
        inputs = {p: pychor.constant(p, i) for i, p in enumerate(parties)}

        result = sum_protocol(parties, inputs)

        # Print the vectors compactly -- 5 parties x 20 field elements is a lot
        # of repr otherwise.
        for p in parties:
            totals = result[p].val
            if totals is not None:
                print(f'{p}: {[int(x) for x in totals]}')

        # Every party contributes the same value in all d slots, so each slot of
        # the reconstructed vector holds the same total: 0 + 1 + 2 + 3 + 4.
        for p in parties:
            check(result[p], [0 + 1 + 2 + 3 + 4] * d, f'totals at {p}')
        return result


if __name__ == '__main__':
    main()
