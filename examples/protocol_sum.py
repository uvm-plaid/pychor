import pychor
import galois
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

GF = galois.GF(2**31-1)
GF = galois.GF(11)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')
Fsum = pychor.Party('Fsum')

@pychor.local_function
def gen_shares(secret):
    s1 = GF.Random()
    s2 = GF(secret) - s1
    return s1, s2

def functionality_sum(in1, in2):
    in1.send(p1, Fsum)
    in2.send(p2, Fsum)
    result = in1 + in2
    result.send(Fsum, p1)
    result.send(Fsum, p2)
    return result

def protocol_sum(in1, in2):
    # Round 1: secret sharing
    p1_s1, p1_s2 = gen_shares(in1).untup(2)
    p2_s1, p2_s2 = gen_shares(in2).untup(2)

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

# Assume p1 is corrupt

def sim_sum_hybrid1(in1, in2, result):
    p1_s1, p1_s2 = gen_shares(in1).untup(2)
    p2_s1, p2_s2 = gen_shares(in2).untup(2)

    p1_s2.send(src=p1, dest=p2)
    p2_s2.send(src=p2, dest=p1)

    p1_sum = p1_s1 + p2_s2
    p2_sum = p1_s2 + p2_s1

    p1_sum.send(src=p1, dest=p2)
    p2_sum.send(src=p2, dest=p1)

    total = p1_sum + p2_sum

    return total

def sim_sum_hybrid2(in1, in2, result):
    p1_s1, p1_s2 = gen_shares(in1).untup(2)
    p2_s1, p2_s2 = gen_shares(in2).untup(2)

    p1_s2.send(src=p1, dest=p2)
    p2_s2.send(src=p2, dest=p1)

    p1_sum = p1_s1 + p2_s2
    p2_sum = p1_s2 + p2_s1

    p1_sum.send(src=p1, dest=p2)
    p2_sum.send(src=p2, dest=p1)

    # total = p1_sum + p2_sum
    # CHANGE: use the functionality's result instead
    total = result

    return total

# CHANGE: we remove the input of the honest party (p2)
def sim_sum_hybrid3(in1, result):
    p1_s1, p1_s2 = gen_shares(in1).untup(2)
    # p2_s1, p2_s2 = gen_shares(in2).untup(2)
    # CHANGE: since we don't know P2's input, let's use
    # the functionality's result to make one up!
    sim_in2 = result - in1
    sim_in2.send(p1, p2, note='Simulator')
    p2_s1, p2_s2 = gen_shares(sim_in2).untup(2)

    p1_s2.send(src=p1, dest=p2)
    p2_s2.send(src=p2, dest=p1)

    p1_sum = p1_s1 + p2_s2
    p2_sum = p1_s2 + p2_s1

    p1_sum.send(src=p1, dest=p2)
    p2_sum.send(src=p2, dest=p1)

    # total = p1_sum + p2_sum
    # CHANGE: use the functionality's result instead
    total = result

    return total

if __name__ == '__main__':
    with pychor.LocalBackend(emit_sequence=True):
        in1 = 5@p1
        in2 = 3@p2

        result = protocol_sum(in1, in2)
        print('Protocol Result:', result)

    with pychor.LocalBackend(emit_sequence=True):
        in1 = 5@p1
        in2 = 3@p2

        functionality_result = functionality_sum(in1, in2)
        print('Functionality Result:', result)

    with pychor.LocalBackend(emit_sequence=True):
        in1 = 5@p1
        in2 = 3@p2

        sim_result = sim_sum_hybrid1(in1, in2, functionality_result)
        print('Simulator Result, Hybrid 1:', sim_result)

    with pychor.LocalBackend(emit_sequence=True):
        in1 = 5@p1
        in2 = 3@p2

        sim_result = sim_sum_hybrid2(in1, in2, functionality_result)
        print('Simulator Result, Hybrid 2:', sim_result)

    with pychor.LocalBackend(emit_sequence=True):
        in1 = 5@p1
        in2 = 3@p2

        sim_result = sim_sum_hybrid3(in1, functionality_result)
        print('Simulator Result, Hybrid 3:', sim_result)
        print("P1's view:", p1.view())

    num_runs = 100
    print('Simulator test!')
    simulator_results = []
    for _ in range(num_runs):
        with pychor.LocalBackend():
            in1 = 5@p1
            in2 = 3@p2

            sim_result = sim_sum_hybrid3(in1, functionality_result)
            simulator_results.append(np.array(p1.view()))

    print('Protocol test!')
    protocol_results = []
    for _ in range(num_runs):
        with pychor.LocalBackend():
            in1 = 5@p1
            in2 = 3@p2

            sim_result = protocol_sum(in1, in2)
            protocol_results.append(np.array(p1.view()))

    simulator_results = np.array(simulator_results)
    print('simulator:', simulator_results.shape)
    protocol_results = np.array(protocol_results)
    print('protocol:', protocol_results.shape)

    print('Are the protocol messages uniformly distributed?')
    K = 11
    counts = np.bincount(protocol_results[:, 0], minlength=K)
    expected = np.full(K, num_runs / K)
    print('Element 1:', stats.chisquare(counts, expected))
    counts = np.bincount(protocol_results[:, 1], minlength=K)
    expected = np.full(K, num_runs / K)
    print('Element 2:', stats.chisquare(counts, expected))

    print('Are the simulator messages uniformly distributed?')
    K = 11
    counts = np.bincount(simulator_results[:, 0], minlength=K)
    expected = np.full(K, num_runs / K)
    print('Element 1:', stats.chisquare(counts, expected))
    counts = np.bincount(simulator_results[:, 1], minlength=K)
    expected = np.full(K, num_runs / K)
    print('Element 2:', stats.chisquare(counts, expected))

    print('Are the simulator messages correlated?')
    print(stats.spearmanr(simulator_results[:, 0], simulator_results[:, 1]))
    print('Are the protocol messages correlated?')
    print(stats.spearmanr(protocol_results[:, 0], protocol_results[:, 1]))

