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

`ForkingTCPBackend` is the localhost testing backend. It forks one local process
per party and wraps `TCPBackend` using deterministic ports.

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

::: pychor.tcp_backend.ForkingTCPBackend
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

::: pychor.choreography.local_function
    options:
      show_root_heading: true
      show_root_full_path: false
