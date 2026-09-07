"""Multiplying secret-shared bits using oblivious transfer.

Addition of additive shares is free, but multiplication is not: the product of
two shared values involves cross terms [u]i*[v]j held by different parties. This
protocol computes each cross term with a single 1-out-of-2 oblivious transfer.

Party i picks a random mask a_ij and offers party j the two-row table
(a_ij, [u]i + a_ij). Party j selects a row using its own share [v]j as the
select bit, and so receives b_ij = [u]i*[v]j + a_ij without revealing which row
it took, while learning nothing about the row it did not take. The mask cancels
when all the terms are summed, so between them the parties hold shares of u*v.
"""

import pychor
from nacl.public import PrivateKey, SealedBox
import galois
from example_backend import backend, check

GF_2 = galois.GF(2)

def ot(sender, receiver, select_bit, options):
    """1-out-of-2 oblivious transfer of one bit.

    The parties are passed in explicitly rather than read off the located
    values, because a located value records every party that can see it and not
    the single owner this protocol needs.
    """
    def gen_keys(select_bit):
        key_pairs = [PrivateKey.generate() for _ in range(2)]
        row_num = int(select_bit)
        saved_key = key_pairs[row_num]
        return row_num, saved_key, [k.public_key for k in key_pairs]

    def encrypt_options(pub_keys, options):
        options_bytes = [int(x).to_bytes(1, 'little') for x in options]
        encrypted_options = [SealedBox(pk).encrypt(x) for pk, x in \
                             zip(pub_keys, options_bytes)]
        return encrypted_options

    def decrypt_result(row_num, saved_key, encrypted_options):
        selected_option = encrypted_options[row_num]
        plaintext = SealedBox(saved_key).decrypt(selected_option)
        return GF_2(int.from_bytes(plaintext, 'little'))

    # ==================================================
    # Protocol: 1-out-of-2 Oblivious Transfer
    # ==================================================

    # generate keys
    row_num, saved_key, pub_keys = (gen_keys@receiver)(select_bit).untup(3)

    # send public keys to sender
    pub_keys.send(receiver, sender, note='public keys')
    pub_keys_r = pub_keys.only(sender)

    # encrypt the options
    encrypted_options = (encrypt_options@sender)(pub_keys_r, options)

    # send them to the receiver
    encrypted_options.send(sender, receiver, note='encrypted rows')
    encrypted_options_r = encrypted_options.only(receiver)

    # decrypt the result
    result = (decrypt_result@receiver)(row_num, saved_key, encrypted_options_r)

    return result


# For every pair (i,j), i≠j, Party i picks random aij and
# lets Party j securely compute bij s.t. aij + bij = [u]i[v]j
# using the naive protocol (a single 1-out-of-2 OT)

# b_ij = [u]i[v]j + a_ij
# inputs: a_ij, u_i, v_j (known)

# party i knows: a_ij, [u]i
# party j knows: [v]j
# select bit is [v]j
# output is b_ij

# sender: i
# receiver: j

# [v]j   b_ij
# ----  ------
#  0     a_ij
#  1     [u]i + a_ij

def f_mult(parties, u_shares, v_shares):
    def b_ij_table(a_ij, u_i):
        return [a_ij, u_i + a_ij]

    received_shares = {p: [] for p in parties}
    for p_i in parties:
        for p_j in parties:
            if p_i != p_j:
                # Locate the mask directly: a local computation needs at least
                # one located input to tell it which party to run at, and
                # generating randomness takes no inputs at all.
                a_ij = pychor.constant(p_i, GF_2.Random())
                table = (b_ij_table@p_i)(a_ij, u_shares[p_i])
                select_bit = v_shares[p_j]
                b_ij = ot(p_i, p_j, select_bit, table)
                received_shares[p_i].append(a_ij)
                received_shares[p_j].append(b_ij)

    result_shares = {}
    for p_i in parties:
        def mult_result(u_i, v_i, shares):
            return u_i*v_i + GF_2(shares).sum()

        result_shares[p_i] = (mult_result@p_i)(u_shares[p_i], v_shares[p_i], received_shares[p_i])
    return result_shares

def make_shares(x, n):
    shares = [GF_2.Random() for _ in range(n-1)]
    shares.append(GF_2(shares).sum() - GF_2(x))
    return shares

def reconstruct(shares):
    return GF_2(shares).sum()

def test_f_mult(parties, dealer, a, b):
    u_shares_d = (make_shares@dealer)(a@dealer, len(parties)).unlist(len(parties))
    v_shares_d = (make_shares@dealer)(b@dealer, len(parties)).unlist(len(parties))

    u_shares = {}
    v_shares = {}
    for p, s in zip(parties, u_shares_d):
        s.send(dealer, p, note='share of u')
        u_shares[p] = s.only(p)
    for p, s in zip(parties, v_shares_d):
        s.send(dealer, p, note='share of v')
        v_shares[p] = s.only(p)

    results = f_mult(parties, u_shares, v_shares)

    results_dealer = []
    for p, s in results.items():
        s.send(p, dealer, note='share of the product')
        results_dealer.append(s.only(dealer))

    return (reconstruct@dealer)(results_dealer)


def main():
    parties = [pychor.Party(f'p{i}') for i in range(6)]
    dealer = pychor.Party('dealer')

    with backend(parties=parties + [dealer]):
        for a in [0, 1]:
            for b in [0, 1]:
                product = test_f_mult(parties, dealer, a, b)
                print(f'{a} * {b} = {product}')
                check(product, a * b, f'{a} * {b}')


if __name__ == '__main__':
    main()
