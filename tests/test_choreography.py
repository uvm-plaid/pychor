"""Tests for the core choreography API.

These run in-process against `LocalBackend`, which plays every party at once, so
they are fast and can inspect both sides of a protocol.
"""

import pytest

import pychor
from pychor import choreography


@pytest.fixture
def parties():
    return pychor.Party('alice'), pychor.Party('bob')


@pytest.fixture
def local(parties):
    """An active LocalBackend over two parties."""
    alice, bob = parties
    with pychor.LocalBackend(parties=[alice, bob]) as backend:
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


def test_matmul_locates_a_value(local, parties):
    alice, _ = parties
    x = 5 @ alice
    assert x.val == 5
    assert x.parties == {alice}


def test_matmul_is_shorthand_for_constant(local, parties):
    alice, _ = parties
    assert (5 @ alice).parties == alice.constant(5).parties


def test_locating_a_callable_gives_a_local_function(local, parties):
    alice, _ = parties
    increment = (lambda v: v + 1) @ alice
    assert increment(5 @ alice).val == 6


def test_constant_rejects_a_foreign_party(local):
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
        pychor.LocalBackend(parties=bad)


def test_party_order_is_preserved():
    alice, bob = pychor.Party('alice'), pychor.Party('bob')
    backend = pychor.LocalBackend(parties=[bob, alice])
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
    with pychor.LocalBackend(parties=[alice, bob]):
        assert choreography.cc is not None
    assert choreography.cc is None


# --------------------------------------------------------------------------
# Ownership: send grows it, only narrows it
# --------------------------------------------------------------------------

def test_send_adds_the_destination_to_the_owners(local, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert x.parties == {alice, bob}


def test_send_records_the_value_in_the_destination_view(local, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert local.views[bob] == [5]
    assert bob.view() == [5]
    assert alice.view() == []


def test_send_requires_the_source_to_own_the_value(local, parties):
    alice, bob = parties
    x = 5 @ alice
    with pytest.raises(AssertionError):
        x.send(src=bob, dest=alice)


def test_only_narrows_ownership(local, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert x.only(bob).parties == {bob}
    # The original is untouched.
    assert x.parties == {alice, bob}


@pytest.mark.parametrize('wrap', [list, set, tuple, frozenset])
def test_only_accepts_a_collection_of_parties(local, parties, wrap):
    """Regression test: this used to raise TypeError on an unhashable argument."""
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    assert x.only(wrap([alice])).parties == {alice}
    assert x.only(wrap([alice, bob])).parties == {alice, bob}


def test_only_rejects_a_non_owner(local, parties):
    alice, bob = parties
    x = 5 @ alice
    with pytest.raises(AssertionError):
        x.only(bob)
    with pytest.raises(AssertionError):
        x.only([bob])


def test_only_rejects_an_empty_collection(local, parties):
    alice, _ = parties
    with pytest.raises(AssertionError):
        (5 @ alice).only([])


def test_only_rejects_a_non_party(local, parties):
    alice, _ = parties
    with pytest.raises(TypeError):
        (5 @ alice).only(42)


# --------------------------------------------------------------------------
# Local computation
# --------------------------------------------------------------------------

def test_locally_runs_at_the_intersection_of_its_inputs(local, parties):
    alice, bob = parties
    x = 5 @ alice
    y = 6 @ bob
    x.send(src=alice, dest=bob)

    result = pychor.locally(lambda a, b: a + b, x, y)
    assert result.val == 11
    assert result.parties == {bob}


def test_locally_rejects_inputs_with_no_common_owner(local, parties):
    alice, bob = parties
    with pytest.raises(AssertionError, match='No participating parties'):
        pychor.locally(lambda a, b: a + b, 5 @ alice, 6 @ bob)


def test_plain_values_place_no_ownership_constraint(local, parties):
    alice, _ = parties
    result = pychor.locally(lambda a, b: a + b, 5 @ alice, 6)
    assert result.val == 11
    assert result.parties == {alice}


def test_locally_accepts_keyword_arguments(local, parties):
    """Regression test: kwargs used to be dropped before reaching the backend."""
    alice, _ = parties
    result = pychor.locally(lambda v, k=0: v + k, 5 @ alice, k=2)
    assert result.val == 7
    assert result.parties == {alice}


def test_locally_accepts_containers_of_located_values(local, parties):
    alice, _ = parties
    result = pychor.locally(lambda pair: pair[0] + pair[1],
                            (5 @ alice, 6 @ alice))
    assert result.val == 11


def test_locally_accepts_a_container_of_plain_values(local, parties):
    """Regression test: an all-scalar container used to fail the owner check."""
    alice, _ = parties
    result = pychor.locally(lambda t, v: sum(t) + v, (1, 2), 5 @ alice)
    assert result.val == 8
    assert result.parties == {alice}


def test_locally_rejects_an_unsupported_value(local, parties):
    alice, _ = parties
    with pytest.raises(Exception, match='Unsupported value'):
        pychor.locally(lambda a, b: a, 5 @ alice, object())


def test_local_function_passes_through_outside_a_backend():
    @pychor.local_function
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_local_function_locates_its_result_inside_a_backend(local, parties):
    alice, _ = parties

    @pychor.local_function
    def add(a, b):
        return a + b

    result = add(5 @ alice, 2)
    assert result.val == 7
    assert result.parties == {alice}


def test_local_function_accepts_keyword_arguments(local, parties):
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
def test_operators_produce_located_results(local, parties, operation, expected):
    alice, _ = parties
    result = operation(5 @ alice, 6 @ alice)
    assert result.val == expected
    assert result.parties == {alice}


def test_true_division(local, parties):
    alice, _ = parties
    assert (6 @ alice / (4 @ alice)).val == 1.5


@pytest.mark.parametrize('operation, expected', [
    (lambda x: 1 + x, 6),
    (lambda x: 1 - x, -4),
    (lambda x: 2 * x, 10),
    (lambda x: 10 / x, 2.0),
])
def test_reflected_operators(local, parties, operation, expected):
    alice, _ = parties
    assert operation(5 @ alice).val == expected


def test_operators_respect_ownership(local, parties):
    alice, bob = parties
    with pytest.raises(AssertionError, match='No participating parties'):
        (5 @ alice) + (6 @ bob)


# --------------------------------------------------------------------------
# Destructuring located collections
# --------------------------------------------------------------------------

def test_untup(local, parties):
    alice, _ = parties
    pair = pychor.locally(lambda v: (v, v + 1), 5 @ alice)
    first, second = pair.untup(2)
    assert (first.val, second.val) == (5, 6)
    assert first.parties == {alice}


def test_unlist(local, parties):
    alice, _ = parties
    located = pychor.locally(lambda v: [v, v + 1, v + 2], 5 @ alice)
    items = located.unlist(3)
    assert [item.val for item in items] == [5, 6, 7]


def test_undict(local, parties):
    alice, _ = parties
    located = pychor.locally(lambda v: {'a': v, 'b': v + 1}, 5 @ alice)
    items = located.undict(['a', 'b'])
    assert {k: v.val for k, v in items.items()} == {'a': 5, 'b': 6}


@pytest.mark.parametrize('destructure', [
    lambda lv: lv.untup(3),      # wrong length
    lambda lv: lv.unlist(2),     # wrong type
])
def test_destructuring_checks_shape(local, parties, destructure):
    alice, _ = parties
    pair = pychor.locally(lambda v: (v, v + 1), 5 @ alice)
    with pytest.raises(AssertionError):
        destructure(pair)


def test_undict_checks_keys(local, parties):
    alice, _ = parties
    located = pychor.locally(lambda v: {'a': v}, 5 @ alice)
    with pytest.raises(AssertionError):
        located.undict(['a', 'b'])


# --------------------------------------------------------------------------
# The sequence diagram
# --------------------------------------------------------------------------

def test_sequence_diagram_records_every_send(local, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    y = pychor.locally(lambda v: v + 6, x.only(bob))
    y.send(src=bob, dest=alice)

    assert local.uml == (
        'sequenceDiagram\n'
        'alice ->> bob : 5\n'
        'bob ->> alice : 11\n'
    )


def test_sequence_diagram_includes_notes(local, parties):
    alice, bob = parties
    (5 @ alice).send(src=alice, dest=bob, note='the answer')
    assert 'alice ->> bob : 5 (the answer)' in local.uml


def test_sequence_diagram_truncates_long_values(local, parties):
    alice, bob = parties
    (('x' * 40) @ alice).send(src=alice, dest=bob)
    assert 'alice ->> bob : xxxxxxxxxx...' in local.uml
    # Only the diagram is abbreviated; the delivered value is intact.
    assert local.views[bob] == ['x' * 40]


def test_views_start_empty_in_each_context(parties):
    alice, bob = parties
    for _ in range(2):
        with pychor.LocalBackend(parties=[alice, bob]) as backend:
            (5 @ alice).send(src=alice, dest=bob)
            assert backend.views[bob] == [5]


# --------------------------------------------------------------------------
# get_val
# --------------------------------------------------------------------------

def test_get_val_unwraps_and_intersects(local, parties):
    alice, bob = parties
    x = 5 @ alice
    x.send(src=alice, dest=bob)
    value, owners = pychor.get_val(x)
    assert value == 5
    assert owners == {alice, bob}


def test_get_val_passes_scalars_through_unconstrained(local):
    assert pychor.get_val(5) == (5, None)
    assert pychor.get_val('hello') == ('hello', None)


def test_get_val_recurses_into_dicts(local, parties):
    alice, _ = parties
    values, owners = pychor.get_val({'a': 5 @ alice, 'b': 6 @ alice})
    assert values == {'a': 5, 'b': 6}
    assert owners == {alice}


# --------------------------------------------------------------------------
# The public API surface
# --------------------------------------------------------------------------

def test_package_exports_only_the_public_api():
    """Regression test: the star-import used to leak its own imports."""
    exported = {name for name in dir(pychor) if not name.startswith('_')}
    leaked = {'socket', 'time', 'dataclass', 'defaultdict', 'wraps',
              'Any', 'Callable', 'Optional', 'Set', 'Iterable', 'Union', 'cc'}
    assert not (exported & leaked), f'leaked names: {sorted(exported & leaked)}'

    for name in ['Party', 'LocatedVal', 'ChoreographyBackend', 'LocalBackend',
                 'TCPBackend', 'ForkingTCPBackend', 'constant', 'locally',
                 'local_function', 'get_val']:
        assert hasattr(pychor, name), f'{name} should be exported'
