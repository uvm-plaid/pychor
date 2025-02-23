import pychor
import galois

GF = galois.GF(7)

def add(a, b):
    return a + b

def sub(a, b):
    return a - b

def sum_ideal(honest, corrupt, input_honest, input_corrupt):
    trusted = pychor.Party('trusted')
    in1 = input_honest >> trusted
    in2 = input_corrupt >> trusted
    result = (add@trusted)(in1, in2)
    return (result >> honest, result >> corrupt)

def sum_protocol(honest, corrupt, input_honest, input_corrupt):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1_r = honest_s1.with_note('input share') >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1.with_note('input share') >> honest

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r)
    sum_honest_r = sum_honest.with_note('sum of shares') >> corrupt
    sum_corrupt_r = sum_corrupt.with_note('sum of shares') >> honest

    # Add results
    total_honest = (add@honest)(sum_honest, sum_corrupt_r)
    total_corrupt = (add@corrupt)(sum_corrupt, sum_honest_r)

    return total_honest, total_corrupt

def sum_sim_h1(honest, corrupt, input_honest, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1_r = honest_s1 >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1 >> honest

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r)
    sum_honest_r = sum_honest >> corrupt
    sum_corrupt_r = sum_corrupt >> honest

    # Add results
    total_honest = (add@honest)(sum_honest, sum_corrupt_r)
    total_corrupt = (add@corrupt)(sum_corrupt, sum_honest_r)

    return total_corrupt

def sum_sim_h2(honest, corrupt, input_honest, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1_r = honest_s1 >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1 >> honest

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r)
    sum_honest_r = sum_honest >> corrupt
    sum_corrupt_r = sum_corrupt >> honest

    # Add results
    #total_honest = (add@honest)(sum_honest, sum_corrupt_r)
    total_corrupt = ideal_result[1] # CHANGE: have that ideal = real result

    return total_corrupt

def sum_sim_h3(honest, corrupt, input_honest, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1_r = honest_s1 >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1 >> honest

    # Round 2: sum and broadcast
    sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    # sum_corrupt = (add@corrupt)(corrupt_s2, honest_s1_r) # NO LONGER NEEDED
    sum_honest_r = sum_honest >> corrupt
    # sum_corrupt_r = sum_corrupt >> honest # DOES NOT AFFECT CORRUPT VIEWS

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt

def sum_sim_h4(honest, corrupt, input_honest, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1_r = honest_s1 >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1 >> honest

    # Round 2: sum and broadcast
    #sum_honest = (add@honest)(honest_s2, corrupt_s1_r)
    # CHANGE: compute the honest sum using ideal result and corrupt share
    sum_honest = (sub@honest)(ideal_result[0], corrupt_s1_r)
    sum_honest_r = sum_honest >> corrupt

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt

def sum_sim_h5(honest, corrupt, input_honest, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    # CHANGE: don't need honest_s2 anymore
    #honest_s2 = (sub@honest)(input_honest, honest_s1)
    honest_s1_r = honest_s1 >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1 >> honest

    # Round 2: sum and broadcast
    sum_honest = (sub@honest)(ideal_result[0], corrupt_s1_r)
    sum_honest_r = sum_honest >> corrupt

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt

# CHANGE: don't need honest input anymore
def sum_sim_h6(honest, corrupt, input_corrupt, ideal_result):
    # Round 1: secret sharing
    honest_s1 = pychor.constant(honest, GF.Random())
    honest_s1_r = honest_s1 >> corrupt

    corrupt_s1 = pychor.constant(corrupt, GF.Random())
    corrupt_s2 = (sub@corrupt)(input_corrupt, corrupt_s1)
    corrupt_s1_r = corrupt_s1 >> honest

    # Round 2: sum and broadcast
    sum_honest = (sub@honest)(ideal_result[0], corrupt_s1_r)
    sum_honest_r = sum_honest >> corrupt

    # Add results
    total_corrupt = ideal_result[1]

    return total_corrupt

if __name__ == '__main__':
    honest = pychor.Party('honest')
    corrupt = pychor.Party('corrupt')

    with pychor.LocalBackend(emit_sequence=True) as b:
        in1 = pychor.constant(honest, GF(2))
        in2 = pychor.constant(corrupt, GF(3))
        result = sum_protocol(honest, corrupt,
                            in1, in2)

        print('protocol result:', result)
        print('protocol corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        ideal_result = sum_ideal(honest, corrupt, in1, in2)
        print('ideal fn:', result)

    with pychor.LocalBackend() as b:
        print('simulator h1:', sum_sim_h1(honest, corrupt, in1, in2, ideal_result))
        print('  h1 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h2:', sum_sim_h2(honest, corrupt, in1, in2, ideal_result))
        print('  h2 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h3:', sum_sim_h3(honest, corrupt, in1, in2, ideal_result))
        print('  h3 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h4:', sum_sim_h4(honest, corrupt, in1, in2, ideal_result))
        print('  h4 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h5:', sum_sim_h5(honest, corrupt, in1, in2, ideal_result))
        print('  h5 corrupt views:', b.views[corrupt])

    with pychor.LocalBackend() as b:
        print('simulator h6:', sum_sim_h6(honest, corrupt, in2, ideal_result))
        print('  h6 corrupt views:', b.views[corrupt])
