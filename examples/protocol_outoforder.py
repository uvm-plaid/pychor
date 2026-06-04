import time

import pychor


alice = pychor.Party('alice')
bob = pychor.Party('bob')
START = time.monotonic()


def log(message):
    elapsed = time.monotonic() - START
    print(f'{elapsed:5.2f}s {message}', flush=True)


@pychor.local_function
def delayed_value(label, delay, seed):
    log(f'alice start {label} computation')
    time.sleep(delay)
    log(f'alice finish {label} computation')
    return f'{label} payload from seed {seed}'

if __name__ == '__main__':
    with pychor.ForkingTCPAsyncBackend(parties=[alice, bob]) as b:
        slow = delayed_value('slow', 1.0, 6@alice)
        fast = delayed_value('fast', 0.1, 42@alice)

        slow.send(src=alice, dest=bob)
        fast.send(src=alice, dest=bob)

        winner = pychor.first([slow, fast])
        log(f'first result: {winner}')
