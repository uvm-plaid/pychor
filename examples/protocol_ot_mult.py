import pychor
from nacl.public import PrivateKey, Box, SealedBox
from dataclasses import dataclass
import galois

GF_2 = galois.GF(2)

def ot(select_bit, options):
    sender = options.party
    receiver = select_bit.party

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
    # Protocol: 1-out-of-4 Oblivious Transfer
    # ==================================================

    # generate keys
    row_num, saved_key, pub_keys = (gen_keys@receiver)(select_bit).untup(3)

    # send public keys to sender
    pub_keys_r = pub_keys >> sender

    # encrypt the options
    encrypted_options = (encrypt_options@sender)(pub_keys_r, options)

    # send them to the receiver
    encrypted_options_r = encrypted_options >> receiver

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
                a_ij = (GF_2.Random@p_i)()
                table = (b_ij_table@p_i)(a_ij, u_shares[p_i])
                select_bit = v_shares[p_j]
                b_ij = ot(select_bit, table)
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

def test_f_mult(a, b):
    u_shares_d = (make_shares@dealer)(a, len(parties)).unlist(len(parties))
    v_shares_d = (make_shares@dealer)(b, len(parties)).unlist(len(parties))

    u_shares = {p: s >> p for p, s in zip(parties, u_shares_d)}
    v_shares = {p: s >> p for p, s in zip(parties, v_shares_d)}

    results = f_mult(parties, u_shares, v_shares)
    results_dealer = [s >> dealer for s in results.values()]
    output = (reconstruct@dealer)(results_dealer)
    return output

if __name__ == '__main__':
    parties = [pychor.Party(f'p{i}') for i in range(6)]
    dealer = pychor.Party('dealer')

    with pychor.LocalBackend():
        for a in [0, 1]:
            for b in [0, 1]:
                print(f'{a} * {b} = {test_f_mult(a, b)}')
