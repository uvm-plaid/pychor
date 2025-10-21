import pychor
import shamir

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
            received_shares[r].append(s >> r)

    # Round 2: sum and broadcast
    received_totals = {p: [] for p in parties}

    for p in parties:
        total = (sum_shares@p)(received_shares[p])
        for r in parties:
            received_totals[r].append(total >> r)

    # Round 3: Add results
    totals = {}
    for p in parties:
        totals[p] = (reconstruct@p)(received_totals[p])

    return totals

if __name__ == '__main__':
    parties = [pychor.Party(f'p{i}') for i in range(1, 6)]

    with pychor.LocalBackend(emit_sequence=True) as b:
        inputs = {p: pychor.constant(p, i) for i, p in enumerate(parties)}

        result = sum_protocol(parties, inputs)
        #print('Results:', result)
        print('Elapsed time:', b.get_elapsed_time())
        print('Cumulative latency:', b.get_cumulative_latency())
