import pychor
import galois

GF = galois.GF(17)

def add(a, b):
    return a + b

def add3(a, b, c):
    return a + b + c

def sub(a, b):
    return a - b

def sum_ideal(honest1, honest2, corrupt, input_honest1, input_honest2, input_corrupt):
    trusted = pychor.Party('trusted')
    in1 = input_honest1 >> trusted
    in2 = input_honest2 >> trusted
    in3 = input_corrupt >> trusted
    result = (add@trusted)((add@trusted)(in1, in2), in3)
    return (result >> honest1, result >> honest2, result >> corrupt)

def gen_shares(party, secret):
    s1 = pychor.constant(party, GF.Random())
    s2 = pychor.constant(party, GF.Random())
    s3 = (sub@party)(secret, (add@party)(s1, s2))
    return s1, s2, s3

def sum_protocol(honest1, honest2, corrupt, input_honest1, input_honest2, input_corrupt):
    # Round 1: secret sharing
    honest1_s1, honest1_s2, honest1_s3 = gen_shares(honest1, input_honest1)
    honest1_s1_r = honest1_s1 >> honest2
    honest1_s2_r = honest1_s2 >> corrupt

    honest2_s1, honest2_s2, honest2_s3 = gen_shares(honest2, input_honest2)
    honest2_s1_r = honest2_s1 >> honest1
    honest2_s2_r = honest2_s2 >> corrupt

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1_r = corrupt_s1 >> honest1
    corrupt_s2_r = corrupt_s2 >> honest2

    # Round 2: sum and broadcast
    sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)

    sum_honest1_honest2 = sum_honest1 >> honest2
    sum_honest1_corrupt = sum_honest1 >> corrupt
    sum_honest2_honest1 = sum_honest2 >> honest1
    sum_honest2_corrupt = sum_honest2 >> corrupt
    sum_corrupt_honest1 = sum_corrupt >> honest1
    sum_corrupt_honest2 = sum_corrupt >> honest2

    # Add results
    total_honest1 = (add3@honest1)(sum_honest1, sum_honest2_honest1, sum_corrupt_honest1)
    total_honest2 = (add3@honest2)(sum_honest2, sum_honest1_honest2, sum_corrupt_honest2)
    total_corrupt = (add3@corrupt)(sum_corrupt, sum_honest1_corrupt, sum_honest2_corrupt)

    return total_honest1, total_honest2, total_corrupt

# Real protocol, with added input for ideal functionality result and only returning corrupt result
def sum_sim_h1(honest1, honest2, corrupt, input_honest1, input_honest2, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest1_s1, honest1_s2, honest1_s3 = gen_shares(honest1, input_honest1)
    honest1_s1_r = honest1_s1 >> honest2
    honest1_s2_r = honest1_s2 >> corrupt

    honest2_s1, honest2_s2, honest2_s3 = gen_shares(honest2, input_honest2)
    honest2_s1_r = honest2_s1 >> honest1
    honest2_s2_r = honest2_s2 >> corrupt

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1_r = corrupt_s1 >> honest1
    corrupt_s2_r = corrupt_s2 >> honest2

    # Round 2: sum and broadcast
    sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)

    sum_honest1_honest2 = sum_honest1 >> honest2
    sum_honest1_corrupt = sum_honest1 >> corrupt
    sum_honest2_honest1 = sum_honest2 >> honest1
    sum_honest2_corrupt = sum_honest2 >> corrupt
    sum_corrupt_honest1 = sum_corrupt >> honest1
    sum_corrupt_honest2 = sum_corrupt >> honest2

    # Add results
    total_honest1 = (add3@honest1)(sum_honest1, sum_honest2_honest1, sum_corrupt_honest1)
    total_honest2 = (add3@honest2)(sum_honest2, sum_honest1_honest2, sum_corrupt_honest2)
    total_corrupt = (add3@corrupt)(sum_corrupt, sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt

# Comment out unused variables - don't contribute to output or corrupt views
def sum_sim_h2(honest1, honest2, corrupt, input_honest1, input_honest2, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest1_s1, honest1_s2, honest1_s3 = gen_shares(honest1, input_honest1)
    honest1_s1_r = honest1_s1 >> honest2
    honest1_s2_r = honest1_s2 >> corrupt

    honest2_s1, honest2_s2, honest2_s3 = gen_shares(honest2, input_honest2)
    honest2_s1_r = honest2_s1 >> honest1
    honest2_s2_r = honest2_s2 >> corrupt

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1_r = corrupt_s1 >> honest1
    corrupt_s2_r = corrupt_s2 >> honest2

    # Round 2: sum and broadcast
    sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)

    # sum_honest1_honest2 = sum_honest1 >> honest2 # not in corrupt views
    sum_honest1_corrupt = sum_honest1 >> corrupt
    # sum_honest2_honest1 = sum_honest2 >> honest1 # not in corrupt views
    sum_honest2_corrupt = sum_honest2 >> corrupt
    # sum_corrupt_honest1 = sum_corrupt >> honest1 # not in corrupt views
    # sum_corrupt_honest2 = sum_corrupt >> honest2 # not in corrupt views

    # Add results
    # total_honest1 = (add3@honest1)(sum_honest1, sum_honest2_honest1, sum_corrupt_honest1)
    # total_honest2 = (add3@honest2)(sum_honest2, sum_honest1_honest2, sum_corrupt_honest2)
    total_corrupt = (add3@corrupt)(sum_corrupt, sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt

# Calculate sum_honest1 as random
#  Doesn't change view distribution because sum_honest1 was the sum of 3 uniformly-distributed values
# Calculate sum_honest2 to satisfy ideal_result = h1 + h2 + c
#  Doesn't change view distribution because protocol must give correct answer
# Eliminate unused variables (honest1_s3 and honest2_s3)
def sum_sim_h3(honest1, honest2, corrupt, input_honest1, input_honest2, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest1_s1, honest1_s2, _ = gen_shares(honest1, input_honest1) # NOTE
    honest1_s1_r = honest1_s1 >> honest2
    honest1_s2_r = honest1_s2 >> corrupt

    honest2_s1, honest2_s2, _ = gen_shares(honest2, input_honest2) # NOTE
    honest2_s1_r = honest2_s1 >> honest1
    honest2_s2_r = honest2_s2 >> corrupt

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1_r = corrupt_s1 >> honest1
    corrupt_s2_r = corrupt_s2 >> honest2

    # Round 2: sum and broadcast
    # sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest1_sim = pychor.constant(corrupt, GF.Random())
    sum_honest1 = sum_honest1_sim >> honest1

    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)
    sum_honest2_sim = (sub@corrupt)(ideal_result[2], (add@corrupt)(sum_honest1_sim, sum_corrupt))
    # sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_honest2 = sum_honest2_sim >> honest2

    # sum_honest1_honest2 = sum_honest1 >> honest2 # not in corrupt views
    sum_honest1_corrupt = sum_honest1 >> corrupt
    # sum_honest2_honest1 = sum_honest2 >> honest1 # not in corrupt views
    sum_honest2_corrupt = sum_honest2 >> corrupt
    # sum_corrupt_honest1 = sum_corrupt >> honest1 # not in corrupt views
    # sum_corrupt_honest2 = sum_corrupt >> honest2 # not in corrupt views

    # Add results
    # total_honest1 = (add3@honest1)(sum_honest1, sum_honest2_honest1, sum_corrupt_honest1)
    # total_honest2 = (add3@honest2)(sum_honest2, sum_honest1_honest2, sum_corrupt_honest2)
    total_corrupt = (add3@corrupt)(sum_corrupt, sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt

# Inline gen_shares, removing unused variables
# The honest inputs are now unused, so we remove them
# NOTE removal of honest inputs
def sum_sim_h4(honest1, honest2, corrupt, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest1_s1 = pychor.constant(honest1, GF.Random())
    honest1_s2 = pychor.constant(honest1, GF.Random())
    honest1_s1_r = honest1_s1 >> honest2
    honest1_s2_r = honest1_s2 >> corrupt

    honest2_s1 = pychor.constant(honest2, GF.Random())
    honest2_s2 = pychor.constant(honest2, GF.Random())
    honest2_s1_r = honest2_s1 >> honest1
    honest2_s2_r = honest2_s2 >> corrupt

    corrupt_s1, corrupt_s2, corrupt_s3 = gen_shares(corrupt, input_corrupt)
    corrupt_s1_r = corrupt_s1 >> honest1
    corrupt_s2_r = corrupt_s2 >> honest2

    # Round 2: sum and broadcast
    # sum_honest1 = (add3@honest1)(honest1_s3, honest2_s1_r, corrupt_s1_r)
    sum_honest1_sim = pychor.constant(corrupt, GF.Random())
    sum_honest1 = sum_honest1_sim >> honest1

    sum_corrupt = (add3@corrupt)(corrupt_s3, honest1_s2_r, honest2_s2_r)
    sum_honest2_sim = (sub@corrupt)(ideal_result[2], (add@corrupt)(sum_honest1_sim, sum_corrupt))
    # sum_honest2 = (add3@honest2)(honest2_s3, honest1_s1_r, corrupt_s2_r)
    sum_honest2 = sum_honest2_sim >> honest2

    # sum_honest1_honest2 = sum_honest1 >> honest2 # not in corrupt views
    sum_honest1_corrupt = sum_honest1 >> corrupt
    # sum_honest2_honest1 = sum_honest2 >> honest1 # not in corrupt views
    sum_honest2_corrupt = sum_honest2 >> corrupt
    # sum_corrupt_honest1 = sum_corrupt >> honest1 # not in corrupt views
    # sum_corrupt_honest2 = sum_corrupt >> honest2 # not in corrupt views

    # Add results
    # total_honest1 = (add3@honest1)(sum_honest1, sum_honest2_honest1, sum_corrupt_honest1)
    # total_honest2 = (add3@honest2)(sum_honest2, sum_honest1_honest2, sum_corrupt_honest2)
    total_corrupt = (add3@corrupt)(sum_corrupt, sum_honest1_corrupt, sum_honest2_corrupt)

    return total_corrupt



if __name__ == '__main__':
    honest1 = pychor.Party('honest1')
    honest2 = pychor.Party('honest2')
    corrupt = pychor.Party('corrupt')

    with pychor.LocalBackend() as b:
        in1 = pychor.constant(honest1, GF(2))
        in2 = pychor.constant(honest2, GF(3))
        in3 = pychor.constant(corrupt, GF(4))
        result = sum_protocol(honest1, honest2, corrupt,
                              in1, in2, in3)

        print('protocol result:', result)
        print('protocol corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        ideal_result = sum_ideal(honest1, honest2, corrupt, in1, in2, in3)
        print('ideal fn:', result)

    with pychor.LocalBackend() as b:
        print('simulator h1:', sum_sim_h1(honest1, honest2, corrupt, in1, in2, in3, ideal_result))
        print('  h1 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h2:', sum_sim_h2(honest1, honest2, corrupt, in1, in2, in3, ideal_result))
        print('  h2 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h3:', sum_sim_h3(honest1, honest2, corrupt, in1, in2, in3, ideal_result))
        print('  h3 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h4:', sum_sim_h4(honest1, honest2, corrupt, in3, ideal_result))
        print('  h4 corrupt views:', b.views[corrupt])
