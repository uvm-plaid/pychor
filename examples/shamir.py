import galois

GF = galois.GF(2**61-1)


# Generate Shamir shares for secret v with threshold t and number of shares n
def share(v, t, n):
    coefficients = GF([GF.Random() for _ in range(t-1)] + [v])
    poly = galois.Poly(coefficients)
    shares = [(GF(x), poly(GF(x))) for x in range(1, n+1)]
    return shares

# Reconstruct the secret from at least t Shamir shares
def reconstruct(shares):
    xs = GF([s[0] for s in shares])
    ys = GF([s[1] for s in shares])
    poly = galois.lagrange_poly(xs, ys)
    #print(poly)
    secret = poly(0)

    return secret

# Multiply two shares
def mult(a, b):
    x1, y1 = a
    x2, y2 = b
    assert x1 == x2
    return (x1, y1 * y2)

# Add two shares
def add(a, b):
    x1, y1 = a
    x2, y2 = b
    assert x1 == x2
    return (x1, y1 + y2)

# Sum up a list of shares, to get a share of the sum
def sum(shares):
    xs = [s[0] for s in shares]
    ys = [s[1] for s in shares]

    # make sure all the xs are the same
    assert xs.count(xs[0]) == len(xs)

    # build the share and output
    return (xs[0], GF(ys).sum())

# Tests
def main():
    # Sharing and reconstruction round-trip.
    shares = share(25, 5, 10)
    v = reconstruct(shares)
    print(v)
    assert v == 25, f'expected 25, got {v}'

    # The threshold is what matters: any t of the n shares reconstruct, and
    # fewer than t reveal nothing about the secret.
    assert reconstruct(shares[:5]) == 25, 'the first t shares should suffice'
    assert reconstruct(shares[5:]) == 25, 'any t shares should suffice'
    assert reconstruct(shares[:4]) != 25, 'fewer than t shares should not work'

    # Addition is local: adding shares point-by-point gives a share of the sum.
    a_shares = share(7, 3, 5)
    b_shares = share(11, 3, 5)
    summed = [add(a, b) for a, b in zip(a_shares, b_shares)]
    assert reconstruct(summed) == 7 + 11, 'add should give shares of the sum'

    # `sum` does the same across a list of shares held by one party.
    assert sum([a_shares[0], b_shares[0]]) == add(a_shares[0], b_shares[0])

    # Multiplication is also local, but it doubles the degree of the underlying
    # polynomial -- so a product of shares from a degree-t sharing needs 2t-1
    # shares to reconstruct, which is why protocol_mult.py has to reduce the
    # degree before the next multiplication.
    c_shares = share(3, 3, 5)
    d_shares = share(4, 3, 5)
    product = [mult(c, d) for c, d in zip(c_shares, d_shares)]
    assert reconstruct(product) == 3 * 4, 'mult should give shares of the product'
    assert reconstruct(product[:3]) != 3 * 4, 'a product needs more shares'

    print('shamir: all checks passed')


if __name__ == '__main__':
    main()
