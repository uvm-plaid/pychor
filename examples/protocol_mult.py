from collections import defaultdict
import pychor
import numpy as np
import shamir


def f_mult(parties, a_shares, b_shares):
    # save x-coords for each party
    x_coords = {p: ((lambda x: x[0])@p)(a_shares[p]) for p in parties}

    # multiply my shares of the two numbers
    mult_results = {p: (shamir.mult@p)(a_shares[p], b_shares[p]) for p in parties}

    # distribute shares of my product
    all_h_i_js = defaultdict(list)
    for p in parties:
        _, y_coord = mult_results[p].untup(2)
        h_is = (shamir.share@p)(y_coord,
                                len(parties)//2,
                                len(parties)).unlist(len(parties))

        for i, pp in enumerate(parties):
            all_h_i_js[pp].append(h_is[i] >> pp)

    # perform the degree reduction
    def reduce_share(x_coord, h_i_js):
        Vi = np.linalg.inv(shamir.GF(np.vander(range(1,len(parties)+1), increasing=True)))
        lambda_js = Vi[0]
        prods = [lambda_j * s[1] for lambda_j, s in zip(lambda_js, h_i_js)]
        return (x_coord, shamir.GF(prods).sum())

    outputs = {p: (reduce_share@p)(x_coords[p], all_h_i_js[p]) for p in parties}
    return outputs

def make_shares(x, n):
    return shamir.share(x, n//2, n)

if __name__ == '__main__':
    parties = [pychor.Party(f'p{i}') for i in range(6)]
    dealer = pychor.Party('dealer')

    a = 5
    b = 3

    with pychor.LocalBackend():
        a_shares_d = (make_shares@dealer)(a, len(parties)).unlist(len(parties))
        b_shares_d = (make_shares@dealer)(b, len(parties)).unlist(len(parties))

        a_shares = {p: s >> p for p, s in zip(parties, a_shares_d)}
        b_shares = {p: s >> p for p, s in zip(parties, b_shares_d)}

        results = f_mult(parties, a_shares, b_shares)
        results_dealer = [s >> dealer for s in results.values()]
        output = (shamir.reconstruct@dealer)(results_dealer)
        print('FINAL RESULT:', output)
