"""Tests for the core choreography API.

These run in-process against `SimulationBackend`, which plays every party at
once, so they are fast and can inspect both sides of a protocol.
"""

import time

import pytest

import pychor
from pychor import choreography


@pytest.fixture
def parties():
    return pychor.Party('alice'), pychor.Party('bob')


@pytest.fixture
def sim(parties):
    """An active SimulationBackend over two parties."""
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob]) as backend:
        yield backend


# --------------------------------------------------------------------------
# Parties and locating values
# --------------------------------------------------------------------------

def test_party_repr_is_its_name():
    assert repr(pychor.Party('alice')) == 'alice'


def test_parties_compare_by_name():
    assert pychor.Party('alice') == pychor.Party('alice')
    assert pychor.Party('alice') != pychor.Party('bob')
    # Frozen dataclasses are hashable, so parties work as dict keys.
    assert len({pychor.Party('alice'), pychor.Party('alice')}) == 1


def test_matmul_locates_a_value(sim, parties):
    alice, _ = parties
    x = 5 @ alice
    assert x.val == 5
    assert x.parties == {alice}


def test_matmul_is_shorthand_for_constant(sim, parties):
    alice, _ = parties
    assert (5 @ alice).parties == alice.constant(5).parties


def test_locating_a_callable_gives_a_local_function(sim, parties):
    alice, _ = parties
    increment = (lambda v: v + 1) @ alice
    assert increment(5 @ alice).val == 6


def test_constant_rejects_a_foreign_party(sim):
    with pytest.raises(ValueError, match='not part of this backend'):
        pychor.constant(pychor.Party('carol'), 5)


@pytest.mark.parametrize('bad, error', [
    ([], ValueError),                                 # no parties
    ([pychor.Party('a'), pychor.Party('a')], ValueError),   # duplicate names
    (['alice'], TypeError),                           # not a Party
    (5, TypeError),                                   # not iterable
])
def test_backend_validates_its_party_list(bad, error):
    with pytest.raises(error):
        pychor.SimulationBackend(parties=bad)


def test_party_order_is_preserved():
    alice, bob = pychor.Party('alice'), pychor.Party('bob')
    backend = pychor.SimulationBackend(parties=[bob, alice])
    assert backend.parties == (bob, alice)


# --------------------------------------------------------------------------
# No active backend
# --------------------------------------------------------------------------

def test_locating_outside_a_backend_fails(parties):
    alice, _ = parties
    with pytest.raises(AssertionError, match='No PyChor backend is running'):
        5 @ alice


def test_backend_is_cleared_on_exit(parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob]):
        assert choreography.cc is not None
    assert choreography.cc is None


# --------------------------------------------------------------------------
# Ownership: send grows it, only narrows it
# --------------------------------------------------------------------------

def test_send_adds_the_destination_to_the_owners(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert x.parties == {alice, bob}


def test_send_records_the_value_in_the_destination_view(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert sim.views[bob] == [5]
    assert bob.view() == [5]
    assert alice.view() == []


def test_send_requires_the_source_to_own_the_value(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    with pytest.raises(AssertionError):
        x.send(src=bob, dest=alice)


def test_only_narrows_ownership(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert x.only(bob).parties == {bob}
    # The original is untouched.
    assert x.parties == {alice, bob}


@pytest.mark.parametrize('wrap', [list, set, tuple, frozenset])
def test_only_accepts_a_collection_of_parties(sim, parties, wrap):
    """Regression test: this used to raise TypeError on an unhashable argument."""
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert x.only(wrap([alice])).parties == {alice}
    assert x.only(wrap([alice, bob])).parties == {alice, bob}


def test_only_rejects_a_non_owner(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    with pytest.raises(AssertionError):
        x.only(bob)
    with pytest.raises(AssertionError):
        x.only([bob])


def test_only_rejects_an_empty_collection(sim, parties):
    alice, _ = parties
    with pytest.raises(AssertionError):
        (5 @ alice).only([])


def test_only_rejects_a_non_party(sim, parties):
    alice, _ = parties
    with pytest.raises(TypeError):
        (5 @ alice).only(42)


# --------------------------------------------------------------------------
# Local computation
# --------------------------------------------------------------------------

def test_locally_runs_at_the_intersection_of_its_inputs(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    y = 6 @ bob
    x.send(src=alice, dest=bob)

    result = pychor.locally(lambda a, b: a + b, x, y)
    assert result.val == 11
    assert result.parties == {bob}


def test_locally_rejects_inputs_with_no_common_owner(sim, parties):
    alice, bob = parties
    with pytest.raises(AssertionError, match='No participating parties'):
        pychor.locally(lambda a, b: a + b, 5 @ alice, 6 @ bob)


def test_plain_values_place_no_ownership_constraint(sim, parties):
    alice, _ = parties
    result = pychor.locally(lambda a, b: a + b, 5 @ alice, 6)
    assert result.val == 11
    assert result.parties == {alice}


def test_locally_accepts_keyword_arguments(sim, parties):
    """Regression test: kwargs used to be dropped before reaching the backend."""
    alice, _ = parties
    result = pychor.locally(lambda v, k=0: v + k, 5 @ alice, k=2)
    assert result.val == 7
    assert result.parties == {alice}


def test_locally_accepts_containers_of_located_values(sim, parties):
    alice, _ = parties
    result = pychor.locally(lambda pair: pair[0] + pair[1],
                            (5 @ alice, 6 @ alice))
    assert result.val == 11


def test_locally_accepts_a_container_of_plain_values(sim, parties):
    """Regression test: an all-scalar container used to fail the owner check."""
    alice, _ = parties
    result = pychor.locally(lambda t, v: sum(t) + v, (1, 2), 5 @ alice)
    assert result.val == 8
    assert result.parties == {alice}


def test_locally_rejects_an_unsupported_value(sim, parties):
    alice, _ = parties
    with pytest.raises(Exception, match='Unsupported value'):
        pychor.locally(lambda a, b: a, 5 @ alice, object())


def test_local_function_passes_through_outside_a_backend():
    @pychor.local_function
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_local_function_locates_its_result_inside_a_backend(sim, parties):
    alice, _ = parties

    @pychor.local_function
    def add(a, b):
        return a + b

    result = add(5 @ alice, 2)
    assert result.val == 7
    assert result.parties == {alice}


def test_local_function_accepts_keyword_arguments(sim, parties):
    """Regression test: the decorator used to drop kwargs."""
    alice, _ = parties

    @pychor.local_function
    def add(value, bonus=0):
        return value + bonus

    assert add(5 @ alice, bonus=3).val == 8


def test_local_function_passes_kwargs_through_outside_a_backend():
    @pychor.local_function
    def add(value, bonus=0):
        return value + bonus

    assert add(5, bonus=3) == 8


def test_local_function_keeps_its_metadata():
    @pychor.local_function
    def documented(value):
        """A docstring."""
        return value

    assert documented.__name__ == 'documented'
    assert documented.__doc__ == 'A docstring.'


# --------------------------------------------------------------------------
# Arithmetic operators
# --------------------------------------------------------------------------

@pytest.mark.parametrize('operation, expected', [
    (lambda x, y: x + y, 11),
    (lambda x, y: x - y, -1),
    (lambda x, y: x * y, 30),
    (lambda x, y: y % x, 1),
    (lambda x, y: -x, -5),
])
def test_operators_produce_located_results(sim, parties, operation, expected):
    alice, _ = parties
    result = operation(5 @ alice, 6 @ alice)
    assert result.val == expected
    assert result.parties == {alice}


def test_true_division(sim, parties):
    alice, _ = parties
    assert (6 @ alice / (4 @ alice)).val == 1.5


@pytest.mark.parametrize('operation, expected', [
    (lambda x: 1 + x, 6),
    (lambda x: 1 - x, -4),
    (lambda x: 2 * x, 10),
    (lambda x: 10 / x, 2.0),
])
def test_reflected_operators(sim, parties, operation, expected):
    alice, _ = parties
    assert operation(5 @ alice).val == expected


def test_operators_respect_ownership(sim, parties):
    alice, bob = parties
    with pytest.raises(AssertionError, match='No participating parties'):
        (5 @ alice) + (6 @ bob)


# --------------------------------------------------------------------------
# Destructuring located collections
# --------------------------------------------------------------------------

def test_untup(sim, parties):
    alice, _ = parties
    pair = pychor.locally(lambda v: (v, v + 1), 5 @ alice)
    first, second = pair.untup(2)
    assert (first.val, second.val) == (5, 6)
    assert first.parties == {alice}


def test_unlist(sim, parties):
    alice, _ = parties
    located = pychor.locally(lambda v: [v, v + 1, v + 2], 5 @ alice)
    items = located.unlist(3)
    assert [item.val for item in items] == [5, 6, 7]


def test_undict(sim, parties):
    alice, _ = parties
    located = pychor.locally(lambda v: {'a': v, 'b': v + 1}, 5 @ alice)
    items = located.undict(['a', 'b'])
    assert {k: v.val for k, v in items.items()} == {'a': 5, 'b': 6}


@pytest.mark.parametrize('destructure', [
    lambda lv: lv.untup(3),      # wrong length
    lambda lv: lv.unlist(2),     # wrong type
])
def test_destructuring_checks_shape(sim, parties, destructure):
    alice, _ = parties
    pair = pychor.locally(lambda v: (v, v + 1), 5 @ alice)
    with pytest.raises(AssertionError):
        destructure(pair)


def test_undict_checks_keys(sim, parties):
    alice, _ = parties
    located = pychor.locally(lambda v: {'a': v}, 5 @ alice)
    with pytest.raises(AssertionError):
        located.undict(['a', 'b'])


# --------------------------------------------------------------------------
# The sequence diagram
# --------------------------------------------------------------------------

def test_sequence_diagram_records_every_send(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    y = pychor.locally(lambda v: v + 6, x.only(bob))
    y.send(src=bob, dest=alice)

    assert sim.uml == (
        'sequenceDiagram\n'
        'alice ->> bob : 5\n'
        'bob ->> alice : 11\n'
    )


def test_sequence_diagram_includes_notes(sim, parties):
    alice, bob = parties
    (5 @ alice).send(src=alice, dest=bob, note='the answer')
    assert 'alice ->> bob : 5 (the answer)' in sim.uml


def test_sequence_diagram_truncates_long_values(sim, parties):
    alice, bob = parties
    (('x' * 40) @ alice).send(src=alice, dest=bob)
    assert 'alice ->> bob : xxxxxxxxxx...' in sim.uml
    # Only the diagram is abbreviated; the delivered value is intact.
    assert sim.views[bob] == ['x' * 40]


def test_views_start_empty_in_each_context(parties):
    alice, bob = parties
    for _ in range(2):
        with pychor.SimulationBackend(parties=[alice, bob]) as backend:
            (5 @ alice).send(src=alice, dest=bob)
            assert backend.views[bob] == [5]


# --------------------------------------------------------------------------
# get_val
# --------------------------------------------------------------------------

def test_get_val_unwraps_and_intersects(sim, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    value, owners = pychor.get_val(x)
    assert value == 5
    assert owners == {alice, bob}


def test_get_val_passes_scalars_through_unconstrained(sim):
    assert pychor.get_val(5) == (5, None)
    assert pychor.get_val('hello') == ('hello', None)


def test_get_val_recurses_into_dicts(sim, parties):
    alice, _ = parties
    values, owners = pychor.get_val({'a': 5 @ alice, 'b': 6 @ alice})
    assert values == {'a': 5, 'b': 6}
    assert owners == {alice}


# --------------------------------------------------------------------------
# Execution timing
# --------------------------------------------------------------------------

def test_timing_starts_at_zero(sim, parties):
    assert set(sim.timing) == set(parties)
    for party in parties:
        assert sim.timing[party] == pychor.PartyTiming()


def test_default_latency_is_a_tenth_of_a_second(sim, parties):
    alice, bob = parties
    assert sim.latency == 0.1
    (5 @ alice).send(src=alice, dest=bob)
    assert sim.timing[bob].clock == pytest.approx(0.1)


def test_send_advances_only_the_receiver(parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob], latency=0.5) as backend:
        (5 @ alice).send(src=alice, dest=bob)

    assert backend.timing[bob].clock == pytest.approx(0.5)
    assert backend.timing[bob].wait_time == pytest.approx(0.5)
    assert backend.timing[bob].messages_received == 1
    assert backend.timing[bob].messages_sent == 0
    assert backend.timing[alice].clock == 0
    assert backend.timing[alice].messages_sent == 1
    assert backend.timing[alice].messages_received == 0


def test_receive_takes_the_later_of_the_two_clocks(parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob], latency=0.5) as backend:
        # Bob is already far ahead, so alice's message does not delay him.
        backend.timing[bob].clock = 5.0
        (5 @ alice).send(src=alice, dest=bob)
        assert backend.timing[bob].clock == 5.0
        assert backend.timing[bob].wait_time == 0

        # Alice, still at time 0, waits for bob's reply to arrive at 5.5.
        (6 @ bob).send(src=bob, dest=alice)
        assert backend.timing[alice].clock == pytest.approx(5.5)
        assert backend.timing[alice].wait_time == pytest.approx(5.5)


def test_latency_mapping_is_per_ordered_pair(parties):
    alice, bob = parties
    latency = {(alice, bob): 1.0, (bob, alice): 0.25}
    with pychor.SimulationBackend(parties=[alice, bob], latency=latency) as backend:
        (5 @ alice).send(src=alice, dest=bob)
        assert backend.timing[bob].clock == pytest.approx(1.0)
        (6 @ bob).send(src=bob, dest=alice)
        assert backend.timing[alice].clock == pytest.approx(1.25)


def test_latency_callable(parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob], latency=lambda a, b: 2.0) as backend:
        (5 @ alice).send(src=alice, dest=bob)
    assert backend.timing[bob].clock == pytest.approx(2.0)


def test_latency_mapping_must_cover_every_pair(parties):
    alice, bob = parties
    with pytest.raises(ValueError, match='missing pairs'):
        pychor.SimulationBackend(parties=[alice, bob], latency={(alice, bob): 1.0})

    carol = pychor.Party('carol')
    with pytest.raises(ValueError, match='not a pair of this backend'):
        pychor.SimulationBackend(
            parties=[alice, bob],
            latency={(alice, bob): 1.0, (bob, alice): 1.0, (alice, carol): 1.0},
        )


@pytest.mark.parametrize('bad, error', [
    ('fast', TypeError),                       # not a number, mapping, or callable
    (-1, ValueError),                          # negative constant
    ({('alice', 'bob'): 1.0}, ValueError),     # keys are not Party objects
])
def test_latency_rejects_bad_values(parties, bad, error):
    with pytest.raises(error):
        pychor.SimulationBackend(parties=list(parties), latency=bad)


def test_latency_mapping_rejects_bad_seconds(parties):
    alice, bob = parties
    with pytest.raises(ValueError, match='non-negative'):
        pychor.SimulationBackend(
            parties=[alice, bob], latency={(alice, bob): -1.0, (bob, alice): 0.0})
    with pytest.raises(TypeError, match='must be a number'):
        pychor.SimulationBackend(
            parties=[alice, bob], latency={(alice, bob): 'slow', (bob, alice): 0.0})


def test_locally_charges_participants_for_execution_time(sim, parties):
    alice, bob = parties
    pychor.locally(lambda v: time.sleep(0.01) or v, 5 @ alice)

    assert sim.timing[alice].compute_time >= 0.01
    assert sim.timing[alice].clock >= 0.01
    assert sim.timing[alice].local_ops == 1
    assert sim.timing[bob] == pychor.PartyTiming()
    # Timing never touches the sequence diagram.
    assert sim.uml == 'sequenceDiagram\n'


def test_locally_charges_every_participant_equally(parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob], latency=0.0) as backend:
        x = 5 @ alice
        x.send(src=alice, dest=bob)
        pychor.locally(lambda v: time.sleep(0.01) or v, x)

    assert backend.timing[alice].local_ops == 1
    assert backend.timing[bob].local_ops == 1
    assert backend.timing[alice].compute_time >= 0.01
    assert backend.timing[alice].compute_time == backend.timing[bob].compute_time


def test_operators_are_timed(sim, parties):
    alice, _ = parties
    x = 5 @ alice
    -(x + 1)
    assert sim.timing[alice].local_ops == 2


def test_clock_is_compute_plus_wait(parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob], latency=0.25) as backend:
        x = 5 @ alice
        x.send(src=alice, dest=bob)          # bob waits until 0.25
        y = x.only(bob) * 2 + 1              # bob computes
        y.send(src=bob, dest=alice)          # alice waits until 0.5 + bob's compute
        z = y + x                            # both compute
        z.send(src=alice, dest=bob)          # bob waits until 0.75 + all compute

    for party in parties:
        t = backend.timing[party]
        assert t.clock == pytest.approx(t.compute_time + t.wait_time)
    assert backend.timing[bob].wait_time == pytest.approx(0.75)
    assert backend.timing[bob].clock == pytest.approx(0.75 + backend.timing[bob].compute_time)
    assert backend.timing[bob].local_ops == 3
    assert backend.timing[alice].local_ops == 1


def test_self_send_is_not_timed(sim, parties):
    alice, _ = parties
    x = 5 @ alice
    x.send(src=alice, dest=alice)
    assert sim.timing[alice] == pychor.PartyTiming()
    # The view still records it, as before.
    assert sim.views[alice] == [5]


def test_send_to_a_foreign_party_is_rejected(sim, parties):
    alice, _ = parties
    with pytest.raises(ValueError, match='not part of this backend'):
        (5 @ alice).send(src=alice, dest=pychor.Party('carol'))


def test_print_timing_summary(capsys, parties):
    alice, bob = parties
    with pychor.SimulationBackend(parties=[alice, bob], latency=0.5) as backend:
        (5 @ alice).send(src=alice, dest=bob)
        backend.print_timing_summary()

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == '=' * 50 and lines[-1] == '=' * 50
    assert lines[1] == 'Execution Timing:'
    assert lines[2] == 'latency model: constant 0.5 s per message'
    assert lines[3].split() == ['party', 'clock', '(s)', 'compute', '(s)', 'wait', '(s)',
                                'local', 'ops', 'sent', 'received']
    assert lines[4].split() == ['alice', '0.000000', '0.000000', '0.000000', '0', '1', '0']
    assert lines[5].split() == ['bob', '0.500000', '0.000000', '0.500000', '0', '0', '1']
    assert lines[6] == 'makespan: 0.500000 s (bob)'


def test_timing_is_fresh_per_backend(parties):
    alice, bob = parties
    for _ in range(2):
        with pychor.SimulationBackend(parties=[alice, bob], latency=1.0) as backend:
            assert backend.timing[bob].clock == 0
            (5 @ alice).send(src=alice, dest=bob)
            assert backend.timing[bob].clock == 1.0


# --------------------------------------------------------------------------
# The public API surface
# --------------------------------------------------------------------------

def test_package_exports_only_the_public_api():
    """Regression test: the star-import used to leak its own imports."""
    exported = {name for name in dir(pychor) if not name.startswith('_')}
    leaked = {'socket', 'time', 'dataclass', 'defaultdict', 'wraps',
              'Any', 'Callable', 'Optional', 'Set', 'Iterable', 'Union', 'cc'}
    assert not (exported & leaked), f'leaked names: {sorted(exported & leaked)}'

    for name in ['Party', 'LocatedVal', 'ChoreographyBackend',
                 'SimulationBackend', 'PartyTiming', 'TCPBackend',
                 'ForkingTCPBackend', 'constant', 'locally', 'local_function',
                 'get_val']:
        assert hasattr(pychor, name), f'{name} should be exported'
