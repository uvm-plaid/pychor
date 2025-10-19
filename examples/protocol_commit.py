import hashlib
import pychor

class Commitment:
    def hash_value(self, value):
        return hashlib.sha256(bytes(str(value), 'utf-8')).hexdigest()

    def __init__(self, sender, receiver, value):
        self.sender = sender
        self.receiver = receiver

        self.hash_val = pychor.locally(self.hash_value, value) # TODO: NONCE!
        self.hash_val.send(sender, receiver, note='hash of committed value')
        self.value = value

    def open(self):
        self.value.send(self.sender, self.receiver, note='original committed value')
        re_hash_val = pychor.locally(self.hash_value, self.value)
        result = self.hash_val == re_hash_val
        return result


if __name__ == '__main__':
    with pychor.LocalBackend():
        sender = pychor.Party('sender')
        receiver = pychor.Party('receiver')

        commitment = Commitment(sender, receiver, pychor.constant(sender, 6))

        print(commitment.open())
