import pychor
import galois

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
            received_shares[r].append(s >> r)

    # Round 2: sum and broadcast
    computed_totals = {p: (sum_shares@p)(received_shares[p]) for p in parties}

    received_totals = {p: [] for p in parties}
    for p in parties:
        for r in parties:
            received_totals[r].append(computed_totals[p] >> r)

    # Round 3: Add results
    totals = {p: (sum_shares@p)(received_totals[p]) for p in parties}

    return totals

if __name__ == '__main__':
    parties = [pychor.Party(f'p{i}') for i in range(1, 6)]

    with pychor.LocalBackend(emit_sequence=True) as b:
        inputs = {p: pychor.constant(p, i) for i, p in enumerate(parties)}

        result = sum_protocol(parties, inputs)
        print('Result:', result)
        print('Elapsed time:', b.get_elapsed_time())
        print('Cumulative latency:', b.get_cumulative_latency())
