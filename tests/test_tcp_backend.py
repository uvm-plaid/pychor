"""Tests for the TCP backends.

The constructor-validation tests run in-process: they never open a socket,
because every check they exercise happens before the mesh is built. The
execution tests run in a subprocess, since `ForkingTCPBackend` forks and its
children exit with `os._exit` -- forking the pytest process would be a mess.
"""

import subprocess
import sys
import textwrap

import pytest

import pychor

ALICE = pychor.Party('alice')
BOB = pychor.Party('bob')
CAROL = pychor.Party('carol')

ADDRESSES = {ALICE: ('127.0.0.1', 10000), BOB: ('127.0.0.1', 10001)}


# --------------------------------------------------------------------------
# Constructor validation, before any socket is opened
# --------------------------------------------------------------------------

def test_me_must_be_a_party():
    with pytest.raises(TypeError, match='me must be a Party'):
        pychor.TCPBackend(parties=[ALICE, BOB], me='alice', addresses=ADDRESSES)


def test_me_must_be_one_of_the_parties():
    with pytest.raises(ValueError, match='not part of this backend'):
        pychor.TCPBackend(parties=[ALICE, BOB], me=CAROL, addresses=ADDRESSES)


def test_addresses_must_be_a_mapping():
    with pytest.raises(TypeError, match='must be a mapping'):
        pychor.TCPBackend(parties=[ALICE, BOB], me=ALICE,
                          addresses=[('127.0.0.1', 10000)])


def test_addresses_must_cover_every_party():
    with pytest.raises(ValueError, match='missing parties'):
        pychor.TCPBackend(parties=[ALICE, BOB], me=ALICE,
                          addresses={ALICE: ('127.0.0.1', 10000)})


def test_addresses_must_not_name_an_unknown_party():
    extra = dict(ADDRESSES, carol=('127.0.0.1', 10002))
    extra[CAROL] = ('127.0.0.1', 10002)
    with pytest.raises(ValueError, match='unknown parties'):
        pychor.TCPBackend(parties=[ALICE, BOB], me=ALICE, addresses=extra)


@pytest.mark.parametrize('address', [
    '127.0.0.1:10000',              # not a tuple
    ('127.0.0.1', 10000, 'extra'),  # wrong length
])
def test_address_must_be_a_host_port_pair(address):
    with pytest.raises(TypeError, match='must be a \\(host, port\\) tuple'):
        pychor.TCPBackend(parties=[ALICE, BOB], me=ALICE,
                          addresses={ALICE: address, BOB: ADDRESSES[BOB]})


def test_host_must_be_a_string():
    with pytest.raises(TypeError, match='host for .* must be a string'):
        pychor.TCPBackend(parties=[ALICE, BOB], me=ALICE,
                          addresses={ALICE: (127, 10000), BOB: ADDRESSES[BOB]})


def test_port_must_be_an_int():
    with pytest.raises(TypeError, match='port for .* must be an int'):
        pychor.TCPBackend(
            parties=[ALICE, BOB], me=ALICE,
            addresses={ALICE: ('127.0.0.1', '10000'), BOB: ADDRESSES[BOB]})


def test_party_list_is_validated_like_any_backend():
    with pytest.raises(ValueError, match='At least one party'):
        pychor.TCPBackend(parties=[], me=ALICE, addresses={})


def test_forking_backend_validates_its_party_list():
    with pytest.raises(ValueError, match='Party names must be unique'):
        pychor.ForkingTCPBackend(parties=[ALICE, pychor.Party('alice')])


def test_connect_timeout_is_reported(monkeypatch):
    """A party with no peers to talk to should time out, not hang."""
    backend = pychor.TCPBackend(
        parties=[ALICE, BOB], me=ALICE,
        addresses={ALICE: ('127.0.0.1', 14899), BOB: ('127.0.0.1', 14898)},
        connect_timeout=0.5,
    )
    with pytest.raises(TimeoutError, match='Timed out connecting alice to bob'):
        backend.__enter__()


# --------------------------------------------------------------------------
# Execution, in a subprocess
# --------------------------------------------------------------------------

def run_script(body, timeout=120):
    """Run a snippet in a fresh interpreter and return its stdout."""
    completed = subprocess.run(
        [sys.executable, '-c', textwrap.dedent(body)],
        capture_output=True, text=True, timeout=timeout,
    )
    if completed.returncode != 0:
        pytest.fail(
            f'subprocess failed (exit {completed.returncode})\n'
            f'--- stdout ---\n{completed.stdout}\n'
            f'--- stderr ---\n{completed.stderr}'
        )
    return completed.stdout


def test_forking_backend_runs_a_protocol():
    output = run_script('''
        import pychor
        alice, bob = pychor.Party('alice'), pychor.Party('bob')
        with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=14700) as b:
            x = 5 @ alice
            x.send(src=alice, dest=bob)
            y = pychor.locally(lambda v: v + 6, x.only(bob))
            y.send(src=bob, dest=alice)
            if b.party == alice:
                print('RESULT', y.val)
    ''')
    assert 'RESULT 11' in output


def test_forking_backend_returns_the_inner_tcp_backend():
    output = run_script('''
        import pychor
        alice, bob = pychor.Party('alice'), pychor.Party('bob')
        with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=14710) as b:
            if b.party == alice:
                print('TYPE', type(b).__name__)
    ''')
    assert 'TYPE TCPBackend' in output


def test_values_are_none_where_they_are_not_owned():
    """The SPMD rule: owner sets agree everywhere, values do not."""
    output = run_script('''
        import pychor
        alice, bob = pychor.Party('alice'), pychor.Party('bob')
        with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=14720) as b:
            x = 5 @ alice
            # Both processes agree on the owner set; only alice has the value.
            print(f'{b.party} owners={sorted(p.name for p in x.parties)} val={x.val}')
    ''')
    assert 'alice owners=[\'alice\'] val=5' in output
    assert 'bob owners=[\'alice\'] val=None' in output


def test_only_the_local_party_has_a_view():
    output = run_script('''
        import pychor
        alice, bob = pychor.Party('alice'), pychor.Party('bob')
        with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=14730) as b:
            x = 5 @ alice
            x.send(src=alice, dest=bob)
            print(f'{b.party} alice_view={alice.view()} bob_view={bob.view()}')
    ''')
    # bob received the message, so only bob's process has it recorded.
    assert 'bob alice_view=[] bob_view=[5]' in output
    assert 'alice alice_view=[] bob_view=[]' in output


def test_child_failure_is_reported_to_the_parent():
    """A failing child must not be silently swallowed."""
    completed = subprocess.run(
        [sys.executable, '-c', textwrap.dedent('''
            import pychor
            alice, bob = pychor.Party('alice'), pychor.Party('bob')
            with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=14740) as b:
                if b.party == bob:
                    raise RuntimeError('bob is unhappy')
        ''')],
        capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode != 0
    assert 'child process failures' in completed.stderr


def test_destructuring_keeps_its_shape_where_unowned():
    output = run_script('''
        import pychor
        alice, bob = pychor.Party('alice'), pychor.Party('bob')
        with pychor.ForkingTCPBackend(parties=[alice, bob], base_port=14750) as b:
            pair = pychor.locally(lambda v: (v, v + 1), 5 @ alice)
            first, second = pair.untup(2)
            print(f'{b.party} {first.val} {second.val}')
    ''')
    assert 'alice 5 6' in output
    assert 'bob None None' in output
