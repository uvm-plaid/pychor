"""BGW multiplication of Shamir-shared values, with degree reduction.

Multiplying two Shamir shares locally gives a share of the product, but on a
polynomial of twice the degree. Left alone, degrees would double with every
multiplication until reconstruction became impossible. The BGW protocol fixes
this by having each party re-share its local product and then take a fixed
linear combination of the re-shared values, which brings the degree back down.

The linear combination is the first row of the inverse Vandermonde matrix, which
is exactly the vector that reads off a polynomial's constant term from its
evaluations.
"""

from collections import defaultdict
import pychor
import numpy as np
import shamir
from example_backend import backend, check


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
            h_is[i].send(p, pp, note='re-shared product')
            all_h_i_js[pp].append(h_is[i].only(pp))

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


def main():
    parties = [pychor.Party(f'p{i}') for i in range(6)]
    dealer = pychor.Party('dealer')

    a = 5
    b = 3

    with backend(parties=parties + [dealer]):
        # The dealer's inputs have to be located before they can be used in a
        # local computation -- a computation over nothing but plain Python values
        # has no party to run at.
        a_shares_d = (make_shares@dealer)(a@dealer, len(parties)).unlist(len(parties))
        b_shares_d = (make_shares@dealer)(b@dealer, len(parties)).unlist(len(parties))

        a_shares = {}
        b_shares = {}
        for p, s in zip(parties, a_shares_d):
            s.send(dealer, p, note='share of a')
            a_shares[p] = s.only(p)
        for p, s in zip(parties, b_shares_d):
            s.send(dealer, p, note='share of b')
            b_shares[p] = s.only(p)

        results = f_mult(parties, a_shares, b_shares)

        results_dealer = []
        for p, s in results.items():
            s.send(p, dealer, note='share of the product')
            results_dealer.append(s.only(dealer))

        output = (shamir.reconstruct@dealer)(results_dealer)
        print('FINAL RESULT:', output)
        check(output, a * b, 'product')
        return output


if __name__ == '__main__':
    main()
