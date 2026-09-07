"""A simulation proof for the three-party sum protocol.

The two-party version of this argument is in protocol_sum_proof.py; read that
one first. The claim and the method are the same -- exhibit a simulator that
reproduces the corrupt party's view using only the ideal functionality's output
-- but with three parties there are two honest parties to account for, and that
changes the interesting step of the proof.

With two parties, the honest party's broadcast was forced: given the ideal
output and the corrupt share, there was only one value it could be. With three,
the two honest broadcasts have a degree of freedom between them. The simulator
exploits it in `sum_sim_h3`: it picks the first honest party's subtotal
uniformly at random, then *solves* for the second so that the three subtotals
add up to the ideal output. That is indistinguishable from the real protocol
because the real subtotal was itself a sum of uniformly distributed shares, and
because a correct protocol must produce the right total either way.

The hybrids:

- `sum_sim_h1` -- the real protocol, restricted to the corrupt party's output.
- `sum_sim_h2` -- drop the messages and totals the corrupt party never sees.
- `sum_sim_h3` -- replace the honest subtotals with a random value and a solved
  value, as described above, and drop the honest parties' third shares.
- `sum_sim_h4` -- inline the share generation for the honest parties. Their
  inputs are now unreferenced, so the signature drops them: this is the
  simulator.

Run the file and compare the `corrupt views` lines. Each is four field elements
drawn from the same distribution, whichever hybrid produced them.
"""

import pychor
import galois
from example_backend import backend, check

GF = galois.GF(17)

honest1 = pychor.Party('honest1')
honest2 = pychor.Party('honest2')
corrupt = pychor.Party('corrupt')

# The trusted third party of the ideal world. It must appear in the backend's
# party list, so it is declared here rather than inside `sum_ideal`.
trusted = pychor.Party('trusted')

PARTIES = [honest1, honest2, corrupt, trusted]

INPUT_HONEST1 = GF(2)
INPUT_HONEST2 = GF(3)
INPUT_CORRUPT = GF(4)
IDEAL_OUTPUT = INPUT_HONEST1 + INPUT_HONEST2 + INPUT_CORRUPT


def add(a, b):
    return a + b

def add3(a, b, c):
    return a + b + c

def sub(a, b):
    return a - b


def make_inputs():
    """Locate the three inputs at their owners."""
    return (pychor.constant(honest1, INPUT_HONEST1),
            pychor.constant(honest2, INPUT_HONEST2),
            pychor.constant(corrupt, INPUT_CORRUPT))


def make_ideal_output():
    """Hand the simulator the ideal functionality's output.

    A simulator is given the ideal output by definition, so locating the value
    directly is faithful -- and unlike reusing a located value from an earlier
    `with` block, it works under every backend.
    """
    return (pychor.constant(honest1, IDEAL_OUTPUT),
            pychor.constant(honest2, IDEAL_OUTPUT),
            pychor.constant(corrupt, IDEAL_OUTPUT))


def gen_shares(party, secret):
    """Split a secret into three additive shares, all held by `party` for now."""
    s1 = pychor.constant(party, GF.Random())
    s2 = pychor.constant(party, GF.Random())
    s3 = (sub@party)(secret, (add@party)(s1, s2))
    return s1, s2, s3


def sum_ideal(input_honest1, input_honest2, input_corrupt):
    """The ideal world: all three parties hand their input to a trusted party."""
    input_honest1.send(honest1, trusted, note='input')
    in1 = input_honest1.only(trusted)

    input_honest2.send(honest2, trusted, note='input')
    in2 = input_honest2.only(trusted)

    input_corrupt.send(corrupt, trusted, note='input')
    in3 = input_corrupt.only(trusted)

    result = (add@trusted)((add@trusted)(in1, in2), in3)

    # One value delivered to three parties, so it is sent three times.
    result.send(trusted, honest1, note='sum')
    result.send(trusted, honest2, note='sum')
    result.send(trusted, corrupt, note='sum')
    return (result.only(honest1), result.only(honest2), result.only(corrupt))


def sum_protocol(input_honest1, input_honest2, input_corrupt):
    """The real protocol: additive sharing, then broadcast the subtotals."""
    # Round 1: secret sharing
    honest1_s1, honest1_s2, honest1_s3 = gen_shares(honest1, input_honest1)
    honest1_s1.send(honest1, honest2, note='input share')
    honest1_s1_r = honest1_s1.only(honest2)
    honest1_s2.send(honest1, corrupt, note='input share')
    honest1_s2_r = honest1_s2.only(corrupt)

    honest2_s1, honest2_s2, honest2_s3 = gen_shares(honest2, input_honest2)
    honest2_s1.send(honest2, honest1, note='input share')
    honest2_s1_r = honest2_s1.only(honest1)
    honest2_s2.send(honest2, corrupt, note='input share')
    honest2_s2_r = honest2_s2.only(corrupt)

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1.send(corrupt, honest1, note='input share')
    corrupt_s1_r = corrupt_s1.only(honest1)
    corrupt_s2.send(corrupt, honest2, note='input share')
    corrupt_s2_r = corrupt_s2.only(honest2)

    # Round 2: sum and broadcast
    sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)

    sum_honest1.send(honest1, honest2, note='subtotal')
    sum_honest1_honest2 = sum_honest1.only(honest2)
    sum_honest1.send(honest1, corrupt, note='subtotal')
    sum_honest1_corrupt = sum_honest1.only(corrupt)

    sum_honest2.send(honest2, honest1, note='subtotal')
    sum_honest2_honest1 = sum_honest2.only(honest1)
    sum_honest2.send(honest2, corrupt, note='subtotal')
    sum_honest2_corrupt = sum_honest2.only(corrupt)

    sum_corrupt.send(corrupt, honest1, note='subtotal')
    sum_corrupt_honest1 = sum_corrupt.only(honest1)
    sum_corrupt.send(corrupt, honest2, note='subtotal')
    sum_corrupt_honest2 = sum_corrupt.only(honest2)

    # Add results
    total_honest1 = (add3@honest1)(sum_honest1.only(honest1),
                                   sum_honest2_honest1, sum_corrupt_honest1)
    total_honest2 = (add3@honest2)(sum_honest2.only(honest2),
                                   sum_honest1_honest2, sum_corrupt_honest2)
    total_corrupt = (add3@corrupt)(sum_corrupt.only(corrupt),
                                   sum_honest1_corrupt, sum_honest2_corrupt)

    return total_honest1, total_honest2, total_corrupt


def sum_sim_h1(input_honest1, input_honest2, input_corrupt, ideal_result):
    """Hybrid 1: the real protocol, keeping only the corrupt party's output."""
    # Round 1: secret sharing
    honest1_s1, honest1_s2, honest1_s3 = gen_shares(honest1, input_honest1)
    honest1_s1.send(honest1, honest2)
    honest1_s1_r = honest1_s1.only(honest2)
    honest1_s2.send(honest1, corrupt)
    honest1_s2_r = honest1_s2.only(corrupt)

    honest2_s1, honest2_s2, honest2_s3 = gen_shares(honest2, input_honest2)
    honest2_s1.send(honest2, honest1)
    honest2_s1_r = honest2_s1.only(honest1)
    honest2_s2.send(honest2, corrupt)
    honest2_s2_r = honest2_s2.only(corrupt)

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1.send(corrupt, honest1)
    corrupt_s1_r = corrupt_s1.only(honest1)
    corrupt_s2.send(corrupt, honest2)
    corrupt_s2_r = corrupt_s2.only(honest2)

    # Round 2: sum and broadcast
    sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)

    sum_honest1.send(honest1, honest2)
    sum_honest1.send(honest1, corrupt)
    sum_honest1_corrupt = sum_honest1.only(corrupt)

    sum_honest2.send(honest2, honest1)
    sum_honest2.send(honest2, corrupt)
    sum_honest2_corrupt = sum_honest2.only(corrupt)

    sum_corrupt.send(corrupt, honest1)
    sum_corrupt.send(corrupt, honest2)

    # Add results
    total_corrupt = (add3@corrupt)(sum_corrupt.only(corrupt),
                                   sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt


def sum_sim_h2(input_honest1, input_honest2, input_corrupt, ideal_result):
    """Hybrid 2: drop everything the corrupt party never sees.

    The messages between the two honest parties, and the honest parties' own
    totals, are invisible from the corrupt party's point of view, so removing
    them cannot change its view.
    """
    # Round 1: secret sharing
    honest1_s1, honest1_s2, honest1_s3 = gen_shares(honest1, input_honest1)
    honest1_s1.send(honest1, honest2)
    honest1_s1_r = honest1_s1.only(honest2)
    honest1_s2.send(honest1, corrupt)
    honest1_s2_r = honest1_s2.only(corrupt)

    honest2_s1, honest2_s2, honest2_s3 = gen_shares(honest2, input_honest2)
    honest2_s1.send(honest2, honest1)
    honest2_s1_r = honest2_s1.only(honest1)
    honest2_s2.send(honest2, corrupt)
    honest2_s2_r = honest2_s2.only(corrupt)

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1.send(corrupt, honest1)
    corrupt_s1_r = corrupt_s1.only(honest1)
    corrupt_s2.send(corrupt, honest2)
    corrupt_s2_r = corrupt_s2.only(honest2)

    # Round 2: sum and broadcast
    sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)

    # honest1 -> honest2 subtotal: not in corrupt views
    sum_honest1.send(honest1, corrupt)
    sum_honest1_corrupt = sum_honest1.only(corrupt)
    # honest2 -> honest1 subtotal: not in corrupt views
    sum_honest2.send(honest2, corrupt)
    sum_honest2_corrupt = sum_honest2.only(corrupt)
    # corrupt -> honest1, corrupt -> honest2 subtotals: not in corrupt views

    # Add results
    # the honest parties' totals are not in corrupt views either
    total_corrupt = (add3@corrupt)(sum_corrupt, sum_honest1_corrupt,
                                   sum_honest2_corrupt)

    return total_corrupt


def sum_sim_h3(input_honest1, input_honest2, input_corrupt, ideal_result):
    """Hybrid 3: simulate the honest subtotals.

    This is the step that carries the proof. `sum_honest1` becomes a uniformly
    random value -- indistinguishable, because in the real protocol it was a sum
    of uniformly distributed shares. `sum_honest2` is then solved for, so that
    the three subtotals add to the ideal output -- indistinguishable, because a
    correct protocol has to produce that total anyway.

    Both are generated at the corrupt party and sent to the honest party that is
    supposed to own them, so that the corrupt party's view still contains a
    message arriving from that party. With the subtotals no longer derived from
    the honest shares, the honest parties' third shares become dead weight.
    """
    # Round 1: secret sharing
    honest1_s1, honest1_s2, _ = gen_shares(honest1, input_honest1)
    honest1_s1.send(honest1, honest2)
    honest1_s2.send(honest1, corrupt)
    honest1_s2_r = honest1_s2.only(corrupt)

    honest2_s1, honest2_s2, _ = gen_shares(honest2, input_honest2)
    honest2_s1.send(honest2, honest1)
    honest2_s2.send(honest2, corrupt)
    honest2_s2_r = honest2_s2.only(corrupt)

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1.send(corrupt, honest1)
    corrupt_s2.send(corrupt, honest2)

    # Round 2: sum and broadcast
    # sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest1_sim = pychor.constant(corrupt, GF.Random())
    sum_honest1_sim.send(corrupt, honest1)
    sum_honest1 = sum_honest1_sim.only(honest1)

    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)
    sum_honest2_sim = (sub@corrupt)(
        ideal_result[2],
        (add@corrupt)(sum_honest1_sim.only(corrupt), sum_corrupt))
    # sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_honest2_sim.send(corrupt, honest2)
    sum_honest2 = sum_honest2_sim.only(honest2)

    sum_honest1.send(honest1, corrupt)
    sum_honest1_corrupt = sum_honest1.only(corrupt)
    sum_honest2.send(honest2, corrupt)
    sum_honest2_corrupt = sum_honest2.only(corrupt)

    # Add results
    total_corrupt = (add3@corrupt)(sum_corrupt.only(corrupt),
                                   sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt


def sum_sim_h4(input_corrupt, ideal_result):
    """Hybrid 4: the simulator.

    The honest parties' shares are now just random values, so `gen_shares` is
    inlined and the third share dropped. Note the signature: neither honest
    input appears. Everything the corrupt party sees is built from randomness
    and the ideal output, which is what the proof set out to show.
    """
    # Round 1: secret sharing
    honest1_s1 = pychor.constant(honest1, GF.Random())
    honest1_s2 = pychor.constant(honest1, GF.Random())
    honest1_s1.send(honest1, honest2)
    honest1_s2.send(honest1, corrupt)
    honest1_s2_r = honest1_s2.only(corrupt)

    honest2_s1 = pychor.constant(honest2, GF.Random())
    honest2_s2 = pychor.constant(honest2, GF.Random())
    honest2_s1.send(honest2, honest1)
    honest2_s2.send(honest2, corrupt)
    honest2_s2_r = honest2_s2.only(corrupt)

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1.send(corrupt, honest1)
    corrupt_s2.send(corrupt, honest2)

    # Round 2: sum and broadcast
    sum_honest1_sim = pychor.constant(corrupt, GF.Random())
    sum_honest1_sim.send(corrupt, honest1)
    sum_honest1 = sum_honest1_sim.only(honest1)

    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)
    sum_honest2_sim = (sub@corrupt)(
        ideal_result[2],
        (add@corrupt)(sum_honest1_sim.only(corrupt), sum_corrupt))
    sum_honest2_sim.send(corrupt, honest2)
    sum_honest2 = sum_honest2_sim.only(honest2)

    sum_honest1.send(honest1, corrupt)
    sum_honest1_corrupt = sum_honest1.only(corrupt)
    sum_honest2.send(honest2, corrupt)
    sum_honest2_corrupt = sum_honest2.only(corrupt)

    # Add results
    total_corrupt = (add3@corrupt)(sum_corrupt.only(corrupt),
                                   sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt


def main():
    # The real protocol.
    with backend(parties=PARTIES) as b:
        in1, in2, in3 = make_inputs()
        totals = sum_protocol(in1, in2, in3)

        print('protocol result:', totals)
        print('protocol corrupt views:', b.views[corrupt])

        for party, total in zip([honest1, honest2, corrupt], totals):
            check(total, IDEAL_OUTPUT, f'protocol total at {party}')

    # The ideal world.
    with backend(parties=PARTIES) as b:
        in1, in2, in3 = make_inputs()
        ideal_totals = sum_ideal(in1, in2, in3)

        print('ideal fn:', ideal_totals)

        for party, total in zip([honest1, honest2, corrupt], ideal_totals):
            check(total, IDEAL_OUTPUT, f'ideal total at {party}')

    # The hybrids, each in its own context so that its views start empty.
    for name, simulator in [('h1', sum_sim_h1), ('h2', sum_sim_h2),
                            ('h3', sum_sim_h3)]:
        with backend(parties=PARTIES) as b:
            in1, in2, in3 = make_inputs()
            result = simulator(in1, in2, in3, make_ideal_output())

            print(f'simulator {name}:', result)
            print(f'  {name} corrupt views:', b.views[corrupt])

            check(result, IDEAL_OUTPUT, f'{name} total at corrupt')

    # Hybrid 4 is the simulator proper: no honest inputs in its signature.
    with backend(parties=PARTIES) as b:
        _, _, in3 = make_inputs()
        result = sum_sim_h4(in3, make_ideal_output())

        print('simulator h4:', result)
        print('  h4 corrupt views:', b.views[corrupt])

        check(result, IDEAL_OUTPUT, 'h4 total at corrupt')


if __name__ == '__main__':
    main()
