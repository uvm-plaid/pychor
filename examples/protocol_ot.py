import pychor
from nacl.public import PrivateKey, PublicKey, Box, SealedBox
from nacl.utils import random
import galois

GF_2 = galois.GF(2)

def ot(sender, receiver, select_bits, options):
    @pychor.local_function
    def gen_keys(select_bits):
        s1, s2 = select_bits
        # Generate 4 random public keys (for which there is no secret key)
        public_keys = [PublicKey(random(PublicKey.SIZE)) for _ in range(4)]
        # Generate 1 actual keypair
        key_pair = PrivateKey.generate()
        # Replace the selected row's (random) public key with the actual public key
        row_num = int(s1)*2 + int(s2)
        public_keys[row_num] = key_pair.public_key

        return row_num, key_pair, public_keys

    @pychor.local_function
    def encrypt_options(pub_keys, options):
        options_bytes = [int(x).to_bytes(1, 'little') for x in options]
        encrypted_options = [SealedBox(pk).encrypt(x) for pk, x in \
                             zip(pub_keys, options_bytes)]
        return encrypted_options

    @pychor.local_function
    def decrypt_result(row_num, saved_key, encrypted_options):
        selected_option = encrypted_options[row_num]
        plaintext = SealedBox(saved_key).decrypt(selected_option)
        return GF_2(int.from_bytes(plaintext, 'little'))

    # ==================================================
    # Protocol: 1-out-of-4 Oblivious Transfer
    # ==================================================

    # generate keys
    row_num, saved_key, pub_keys = gen_keys(select_bits).untup(3)

    # send public keys to sender
    pub_keys.send(receiver, sender, note='public keys')

    # encrypt the options
    encrypted_options = encrypt_options(pub_keys, options)

    # send them to the receiver
    encrypted_options.send(sender, receiver, note='encrypted values')

    # decrypt the result
    result = decrypt_result(row_num, saved_key, encrypted_options)

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

