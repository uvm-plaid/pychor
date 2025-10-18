import pychor
from nacl.public import PrivateKey, Box, SealedBox
import galois

GF_2 = galois.GF(2)

def ot(sender, receiver, select_bits, options):
    def gen_keys(select_bits):
        s1, s2 = select_bits
        key_pairs = [PrivateKey.generate() for _ in range(4)]
        row_num = int(s1)*2 + int(s2)
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
    row_num, saved_key, pub_keys = pychor.locally(gen_keys, select_bits).untup(3)

    # send public keys to sender
    pub_keys.send(sender, receiver, note='public keys')

    # encrypt the options
    encrypted_options = pychor.locally(encrypt_options, pub_keys, options)

    # send them to the receiver
    encrypted_options.send(sender, receiver, note='encrypted values')

    # decrypt the result
    result = pychor.locally(decrypt_result, row_num, saved_key, encrypted_options)

    return result

if __name__ == '__main__':
    receiver = pychor.Party('receiver')
    sender = pychor.Party('sender')

    with pychor.LocalBackend(emit_sequence=True) as b:
        select_bits = receiver.constant(GF_2([1, 1]))
        options = sender.constant(GF_2([0, 0, 0, 1]))
        result = ot(sender, receiver, select_bits, options)
        print('result:', result)
        print('views:')
        for k, vs in b.views.items():
            print(k)
            for v in vs:
                print('  ' + str(v))

