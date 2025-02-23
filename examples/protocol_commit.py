import hashlib
import pychor

class Commitment:
    def hash_value(self, value):
        return hashlib.sha256(bytes(str(value), 'utf-8')).hexdigest()

    def __init__(self, sender, receiver, value):
        self.sender = sender
        self.receiver = receiver

        hash_val = (self.hash_value@sender)(value) # TODO: NONCE!
        self.hash_val_r = hash_val.with_note('hash of committed value') >> receiver
        self.value = value

    def open(self):
        value_r = self.value.with_note('original committed value') >> self.receiver
        re_hash_val = (self.hash_value@self.receiver)(value_r)
        result = ((lambda a,b: a == b)@self.receiver)(self.hash_val_r, re_hash_val)
        return result, value_r


if __name__ == '__main__':
    with pychor.LocalBackend():
        sender = pychor.Party('sender')
        receiver = pychor.Party('receiver')

        commitment = Commitment(sender, receiver, pychor.constant(sender, 6))

        print(commitment.open())
