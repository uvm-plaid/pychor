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
if __name__ == '__main__':
    shares = share(25, 5, 10)
    v = reconstruct(shares)
    print(v)
