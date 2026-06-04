# API Reference

The generated reference below covers the main choreography API and bundled
backends.

## TCP backends

`TCPBackend` runs one party in the current process. For a deployment, run the
same program once per party and pass the local party as `me` plus an address map
for every party:

```python
addresses = {
    alice: ("10.0.0.1", 10000),
    bob: ("10.0.0.2", 10000),
}

with pychor.TCPBackend(parties=[alice, bob], me=alice, addresses=addresses):
    ...
```

`TCPAsyncBackend` uses the same deployment shape, but schedules sends and local
computations as futures. It blocks only when a value is observed or when the
backend context exits and outstanding sends must complete.

`pychor.first([...])` returns a located value that resolves to the first
successful candidate. With `TCPAsyncBackend`, forcing the result races the
candidate futures in parallel; synchronous backends choose the first candidate
in program order.

`ForkingTCPBackend` and `ForkingTCPAsyncBackend` are localhost testing backends.
They fork one local process per party and wrap the corresponding single-party
TCP backend using deterministic ports.

::: pychor.choreography.Party
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.LocatedVal
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.ChoreographyBackend
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.LocalBackend
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.tcp_backend.TCPBackend
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.tcp_backend.TCPAsyncBackend
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.tcp_backend.ForkingTCPBackend
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.tcp_backend.ForkingTCPAsyncBackend
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.constant
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.locally
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.first
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.local_function
    options:
      show_root_heading: true
      show_root_full_path: false
