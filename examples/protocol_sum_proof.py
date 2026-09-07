"""A hand-written simulation proof for the two-party sum protocol.

This example is a security argument written as an executable program. The claim
is that the two-party sum protocol reveals nothing to a corrupt participant
beyond the sum it is entitled to learn. The way to prove that is to exhibit a
*simulator*: a program that produces the same view for the corrupt party while
using only the ideal functionality's output, never the honest party's input. If
the two views are indistinguishable, everything the corrupt party saw it could
have generated itself, so the protocol leaked nothing.

The proof proceeds by a *hybrid argument*. Rather than jumping straight from the
real protocol to the simulator, it walks there in six small steps, each a
complete program you can run and compare against its neighbour:

- `sum_sim_h1` -- the real protocol, restricted to the corrupt party's output.
- `sum_sim_h2` -- take the total from the ideal functionality instead of
  computing it. Same distribution, because the protocol is correct.
- `sum_sim_h3` -- drop the corrupt party's own sum, which no longer feeds
  anything the corrupt party sees.
- `sum_sim_h4` -- derive the honest party's broadcast from the ideal output and
  the corrupt share, instead of from the honest input.
- `sum_sim_h5` -- drop the honest party's second share, now unused.
- `sum_sim_h6` -- drop the honest input entirely. Nothing references it, which is
  the point: this program is a simulator.

Because each step preserves the corrupt party's view, the real protocol's view
and the simulator's are indistinguishable. Run this file and compare the printed
`corrupt views` line for each hybrid: the values differ run to run because the
shares are random, but they are drawn from the same distribution.
`protocol_sum.py` makes the same argument for three parties and checks the
distributions statistically rather than by eye.
"""

import pychor
import galois
from example_backend import backend, check

GF = galois.GF(7)

honest = pychor.Party('honest')
corrupt = pychor.Party('corrupt')

# The trusted third party of the ideal world. It has to be a real party in the
# backend's party list, so it is declared here rather than inside `sum_ideal`.
trusted = pychor.Party('trusted')

PARTIES = [honest, corrupt, trusted]

# The two inputs, as plain field elements. `make_inputs` locates them fresh in
# each backend context, because located values do not outlive their `with` block.
INPUT_HONEST = GF(2)
INPUT_CORRUPT = GF(3)
IDEAL_OUTPUT = INPUT_HONEST + INPUT_CORRUPT


def add(a, b):
    return a + b

def sub(a, b):
    return a - b


def make_inputs():
    """Locate the two inputs at their owners."""
    return (pychor.constant(honest, INPUT_HONEST),
            pychor.constant(corrupt, INPUT_CORRUPT))


def make_ideal_output():
    """Hand the simulator the ideal functionality's output.

    A simulator is *given* the output of the ideal functionality -- that is what
    distinguishes it from an adversary. Locating the value directly models that
    faithfully, and unlike reusing a located value from an earlier `with` block
    it works under every backend.
    """
    return (pychor.constant(honest, IDEAL_OUTPUT),
            pychor.constant(corrupt, IDEAL_OUTPUT))


def sum_ideal(input_honest, input_corrupt):
    """The ideal world: both parties hand their input to a trusted third party."""
    input_honest.send(honest, trusted, note='input')
    in1 = input_honest.only(trusted)

    input_corrupt.send(corrupt, trusted, note='input')
    in2 = input_corrupt.only(trusted)

    result = (add@trusted)(in1, in2)

    # One value delivered to two parties, so it is sent twice.
    result.send(trusted, honest, note='sum')
    result.send(trusted, corrupt, note='sum')
    return (result.only(honest), result.only(corrupt))


def sum_protocol(input_honest, input_corrupt):
    """The real protocol: additive sharing, then broadcast the partial sums."""
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1.send(honest, corrupt, note='input share')
    honest_s1_r = honest_s1.only(corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest, note='input share')
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r)
    sum_honest.send(honest, corrupt, note='sum of shares')
    sum_honest_r = sum_honest.only(corrupt)
    sum_corrupt.send(corrupt, honest, note='sum of shares')
    sum_corrupt_r = sum_corrupt.only(honest)

    # Add results
    total_honest = (add@honest)(sum_honest.only(honest), sum_corrupt_r)
    total_corrupt = (add@corrupt)(sum_corrupt.only(corrupt), sum_honest_r)

    return total_honest, total_corrupt


def sum_sim_h1(input_honest, input_corrupt, ideal_result):
    """Hybrid 1: the real protocol, keeping only the corrupt party's output."""
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1.send(honest, corrupt)
    honest_s1_r = honest_s1.only(corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest)
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r)
    sum_honest.send(honest, corrupt)
    sum_honest_r = sum_honest.only(corrupt)
    sum_corrupt.send(corrupt, honest)

    # Add results
    total_corrupt = (add@corrupt)(sum_corrupt.only(corrupt), sum_honest_r)

    return total_corrupt


def sum_sim_h2(input_honest, input_corrupt, ideal_result):
    """Hybrid 2: take the total from the ideal functionality.

    The protocol is correct, so the total it computes and the ideal output are
    the same value -- swapping one for the other cannot change the view.
    """
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1.send(honest, corrupt)
    honest_s1_r = honest_s1.only(corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest)
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r)
    sum_honest.send(honest, corrupt)
    sum_corrupt.send(corrupt, honest)

    # Add results
    # total_corrupt = (add@corrupt)(sum_corrupt, sum_honest_r)
    total_corrupt = ideal_result[1]  # CHANGE: use the ideal result

    return total_corrupt


def sum_sim_h3(input_honest, input_corrupt, ideal_result):
    """Hybrid 3: stop computing the corrupt party's own sum.

    Nothing the corrupt party sees depends on it any more, so removing it is
    invisible from the corrupt party's point of view.
    """
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1.send(honest, corrupt)
    honest_s1_r = honest_s1.only(corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest)
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    # sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r) # NO LONGER NEEDED
    sum_honest.send(honest, corrupt)
    # the corrupt party's broadcast does not affect the corrupt party's view

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt


def sum_sim_h4(input_honest, input_corrupt, ideal_result):
    """Hybrid 4: derive the honest broadcast from the ideal output.

    Instead of summing the honest party's real shares, work backwards from the
    ideal output and the corrupt party's share. The value broadcast is the same,
    so the view is unchanged -- but the honest input is now used one step later.
    """
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1.send(honest, corrupt)
    honest_s1_r = honest_s1.only(corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest)
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    # sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    # CHANGE: compute the honest sum from the ideal result and the corrupt share
    sum_honest = (sub@honest)(ideal_result[0], corrupt_s1_r)
    sum_honest.send(honest, corrupt)

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt


def sum_sim_h5(input_honest, input_corrupt, ideal_result):
    """Hybrid 5: drop the honest party's second share, now unused."""
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    # CHANGE: honest_s2 is no longer needed
    # honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1.send(honest, corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest)
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    sum_honest = (sub@honest)(ideal_result[0], corrupt_s1_r)
    sum_honest.send(honest, corrupt)

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt


def sum_sim_h6(input_corrupt, ideal_result):
    """Hybrid 6: the simulator.

    Note the signature: the honest party's input is gone. Everything the corrupt
    party sees is generated from randomness and the ideal output alone, which is
    exactly the statement that the protocol leaks nothing else.
    """
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s1.send(honest, corrupt)

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1.send(corrupt, honest)
    corrupt_s1_r = corrupt_s1.only(honest)

    # Round 2: sum and broadcast
    sum_honest = (sub@honest)(ideal_result[0], corrupt_s1_r)
    sum_honest.send(honest, corrupt)

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt


def main():
    # The real protocol.
    with backend(parties=PARTIES) as b:
        in1, in2 = make_inputs()
        total_honest, total_corrupt = sum_protocol(in1, in2)

        print('protocol result:', (total_honest, total_corrupt))
        print('protocol corrupt views:', b.views[corrupt])

        check(total_honest, IDEAL_OUTPUT, 'protocol total at honest')
        check(total_corrupt, IDEAL_OUTPUT, 'protocol total at corrupt')

    # The ideal world.
    with backend(parties=PARTIES) as b:
        in1, in2 = make_inputs()
        ideal_honest, ideal_corrupt = sum_ideal(in1, in2)

        print('ideal fn:', (ideal_honest, ideal_corrupt))

        check(ideal_honest, IDEAL_OUTPUT, 'ideal total at honest')
        check(ideal_corrupt, IDEAL_OUTPUT, 'ideal total at corrupt')

    # The hybrids, each in its own context so that its views start empty.
    hybrids = [
        ('h1', sum_sim_h1),
        ('h2', sum_sim_h2),
        ('h3', sum_sim_h3),
        ('h4', sum_sim_h4),
        ('h5', sum_sim_h5),
    ]
    for name, simulator in hybrids:
        with backend(parties=PARTIES) as b:
            in1, in2 = make_inputs()
            result = simulator(in1, in2, make_ideal_output())

            print(f'simulator {name}:', result)
            print(f'  {name} corrupt views:', b.views[corrupt])

            check(result, IDEAL_OUTPUT, f'{name} total at corrupt')

    # Hybrid 6 is the simulator proper: no honest input in its signature.
    with backend(parties=PARTIES) as b:
        _, in2 = make_inputs()
        result = sum_sim_h6(in2, make_ideal_output())

        print('simulator h6:', result)
        print('  h6 corrupt views:', b.views[corrupt])

        check(result, IDEAL_OUTPUT, 'h6 total at corrupt')


if __name__ == '__main__':
    main()
