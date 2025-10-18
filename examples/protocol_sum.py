import pychor
import galois

GF = galois.GF(2**31-1)
GF = galois.GF(11)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')

def gen_shares(secret):
    s1 = GF.Random()
    s2 = GF(secret) - s1
    return s1, s2

def sum_protocol(in1, in2):
    # Round 1: secret sharing
    p1_s1, p1_s2 = pychor.locally(gen_shares, in1).untup(2)
    p2_s1, p2_s2 = pychor.locally(gen_shares, in2).untup(2)

    p1_s2.send(src=p1, dest=p2)
    p2_s2.send(src=p2, dest=p1)

    # Round 2: sum and broadcast
    p1_sum = p1_s1 + p2_s2
    p2_sum = p1_s2 + p2_s1

    p1_sum.send(src=p1, dest=p2)
    p2_sum.send(src=p2, dest=p1)

    # Round 3: Add results
    total = p1_sum + p2_sum

    return total

if __name__ == '__main__':
    with pychor.LocalBackend(emit_sequence=True) as b:
        in1 = 5@p1
        in2 = 3@p2

        result = sum_protocol(in1, in2)
        print('Result:', result)
