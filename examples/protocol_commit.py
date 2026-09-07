"""A hash-based commitment scheme.

Committing to a value means binding yourself to it without revealing it. The
sender hashes the value and sends the hash; later it sends the value itself, and
the receiver re-hashes to confirm it matches. The hash reveals nothing about the
value on its own, but the sender cannot change its mind afterwards without
producing a different hash.
"""

import hashlib
import pychor
from example_backend import backend

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


def main():
    sender = pychor.Party('sender')
    receiver = pychor.Party('receiver')

    with backend(parties=[sender, receiver]):
        commitment = Commitment(sender, receiver, pychor.constant(sender, 6))

        # `open` compares two located hashes, so it returns a plain bool: the
        # receiver either accepts the opened value or it does not.
        opened = commitment.open()
        print(opened)
        assert opened, 'the receiver should accept an honestly opened commitment'
        return opened


if __name__ == '__main__':
    main()
