"""A simulation proof for the two-party sum, checked statistically.

protocol_sum_proof.py makes this argument by eye, comparing the corrupt party's
view across a sequence of hybrids. This file makes the same argument for the sum
protocol and then *measures* it: it runs the real protocol and the final
simulator many times, collects p1's view from each run, and tests whether the
two collections of messages look alike.

The security claim is that p1 learns nothing about p2's input beyond the total,
so the test is that the messages p1 receives are uniformly distributed over the
field and uncorrelated with each other -- and that the real protocol and the
simulator agree on this. A chi-square test checks uniformity and a Spearman
coefficient checks correlation. High p-values mean the data is consistent with
messages that carry no information.

The sample size comes from PYCHOR_SUM_RUNS (default 20, which is enough to see
the shape). The statistical claims want a few hundred; the test suite runs 100.
"""

import os
import pychor
import galois
import numpy as np
from scipy import stats
from example_backend import backend, check

# A small field keeps the chi-square buckets well populated at modest sample
# sizes. The protocol itself works over any prime field.
GF = galois.GF(11)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')
Fsum = pychor.Party('Fsum')

PARTIES = [p1, p2, Fsum]

INPUT_P1 = 5
INPUT_P2 = 3
IDEAL_OUTPUT = INPUT_P1 + INPUT_P2

# How many samples the distribution comparison draws.
NUM_RUNS = int(os.environ.get('PYCHOR_SUM_RUNS', '20'))


def make_inputs():
    """Locate the two inputs at their owners."""
    return INPUT_P1@p1, INPUT_P2@p2


def make_ideal_output():
    """Hand a simulator the ideal functionality's output.

    A simulator is given the ideal output by definition. Locating it afresh in
    each backend context also keeps the hybrids independent -- reusing a located
    value across `with` blocks would carry one run's state into the next.
    """
    # A plain int, matching what `functionality_sum` produces from the inputs:
    # `gen_shares` lifts it into the field when it shares it.
    return pychor.constant(p1, IDEAL_OUTPUT)

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

def run_hybrids():
    """Run the protocol, the ideal functionality, and the three hybrids once."""
    with backend(parties=PARTIES):
        in1, in2 = make_inputs()
        result = protocol_sum(in1, in2)
        print('Protocol Result:', result)
        check(result, IDEAL_OUTPUT, 'protocol total')

    with backend(parties=PARTIES):
        in1, in2 = make_inputs()
        functionality_result = functionality_sum(in1, in2)
        print('Functionality Result:', functionality_result)
        check(functionality_result, IDEAL_OUTPUT, 'functionality total')

    with backend(parties=PARTIES):
        in1, in2 = make_inputs()
        sim_result = sim_sum_hybrid1(in1, in2, make_ideal_output())
        print('Simulator Result, Hybrid 1:', sim_result)
        check(sim_result, IDEAL_OUTPUT, 'hybrid 1 total')

    with backend(parties=PARTIES):
        in1, in2 = make_inputs()
        sim_result = sim_sum_hybrid2(in1, in2, make_ideal_output())
        print('Simulator Result, Hybrid 2:', sim_result)
        check(sim_result, IDEAL_OUTPUT, 'hybrid 2 total')

    with backend(parties=PARTIES):
        in1, _ = make_inputs()
        sim_result = sim_sum_hybrid3(in1, make_ideal_output())
        print('Simulator Result, Hybrid 3:', sim_result)
        print("P1's view:", p1.view())
        check(sim_result, IDEAL_OUTPUT, 'hybrid 3 total')


def sample_views(runner, num_runs):
    """Collect p1's view over `num_runs` independent runs.

    Each run needs its own backend context, because views start empty in every
    context -- that is what makes the samples independent.
    """
    samples = []
    for _ in range(num_runs):
        with backend(parties=PARTIES):
            runner()
            samples.append(np.array(p1.view()))
    return np.array(samples)


def compare_view_distributions(num_runs=NUM_RUNS):
    """Test whether the simulator's messages look like the protocol's."""
    def run_simulator():
        in1, _ = make_inputs()
        sim_sum_hybrid3(in1, make_ideal_output())

    def run_protocol():
        in1, in2 = make_inputs()
        protocol_sum(in1, in2)

    print('Simulator test!')
    simulator_results = sample_views(run_simulator, num_runs)
    print('Protocol test!')
    protocol_results = sample_views(run_protocol, num_runs)

    print('simulator:', simulator_results.shape)
    print('protocol:', protocol_results.shape)

    # Only the process playing p1 has a populated view, so the other parties'
    # processes have nothing to compare.
    if simulator_results.shape[1] == 0:
        print('(no p1 view in this process -- skipping the distribution tests)')
        return

    K = GF.order

    def uniformity(name, samples):
        print(f'Are the {name} messages uniformly distributed?')
        for i in range(samples.shape[1]):
            counts = np.bincount(samples[:, i], minlength=K)
            expected = np.full(K, num_runs / K)
            print(f'Element {i + 1}:', stats.chisquare(counts, expected))

    uniformity('protocol', protocol_results)
    uniformity('simulator', simulator_results)

    print('Are the simulator messages correlated?')
    print(stats.spearmanr(simulator_results[:, 0], simulator_results[:, 1]))
    print('Are the protocol messages correlated?')
    print(stats.spearmanr(protocol_results[:, 0], protocol_results[:, 1]))


def main():
    run_hybrids()
    compare_view_distributions()


if __name__ == '__main__':
    main()
