# API Reference

Generated reference for PyChor's public objects. Everything listed here is
re-exported from the `pychor` package, so `pychor.Party` and
`pychor.choreography.Party` are the same class.

For the ideas behind these objects, read [Concepts](concepts.md); for choosing
and configuring a backend, read [Backends](backends.md).

## Core API

The objects a choreography is written with: parties to own values, located
values to carry them, and the three functions that run ordinary Python code at a
party.

::: pychor.choreography.Party
    options:
      show_root_heading: true
      show_root_full_path: false

::: pychor.choreography.LocatedVal
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

::: pychor.choreography.get_val
    options:
      show_root_heading: true
      show_root_full_path: false

## Backends

A backend decides what locating, computing, and sending mean, and is entered as
a context manager. `ChoreographyBackend` is the interface to implement for a new
one — see
[Writing a custom backend](backends.md#writing-a-custom-backend).

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

## Transport

The wire format used by the TCP backends. Choreographies do not use this
directly; it is documented for anyone implementing a backend of their own or
auditing what travels over the network.

::: pychor.object_stream.ObjectStream
    options:
      show_root_heading: true
      show_root_full_path: false
