# WIP

import pychor
import random
from protocol_commit import Commitment

def assert_true(x):
    assert x

def commit(prover, verifier, edges, coloring):
    vertices = coloring.keys()
    colors = ['red', 'green', 'blue']

    def shuffle_coloring(coloring):
        # construct a shuffled set of colors
        shuffled_colors = ['red', 'green', 'blue']
        random.shuffle(shuffled_colors)

        # map colors to shuffled colors
        color_mapping = {k : v for k, v in zip(colors, shuffled_colors)}

        # construct a coloring with the shuffled colors
        shuffled_coloring = {vertex : color_mapping[color] for vertex, color in coloring.items()}

        return shuffled_coloring

    shuffled_coloring = (shuffle_coloring@prover)(coloring)

    # commit to the shuffled colors
    commitments = {vertex : Commitment(prover, verifier, color)
                   for vertex, color in shuffled_coloring.undict(vertices).items()}

    return commitments

def challenge(prover, verifier, edges):
    def pick_edge(edges):
        idx = random.randint(0, len(edges)-1)
        return edges[idx]

    edge = (pick_edge@verifier)(edges)
    return edge, edge.with_note('challenge') >> prover

def response(prover, verifier, edge_r, commitments):
    v1, v2 = edge_r.unlist(2)
    c1 = ((lambda x: commitments[x])@prover)(v1)
    c2 = ((lambda x: commitments[x])@prover)(v2)

    return c1.val.open(), c2.val.open()

def check(prover, verifier, c1, c2):
    r1, color1 = c1
    r2, color2 = c2

    ((lambda x: assert_true(x))@verifier)(r1)
    ((lambda x: assert_true(x))@verifier)(r2)
    ((lambda x,y: assert_true(x != y))@verifier)(color1, color2)

def run_protocol():
    prover = pychor.Party('prover')
    verifier = pychor.Party('verifier')

    coloring = {
        # outer five nodes, clockwise from top
        0: 'red',
        1: 'blue',
        2: 'green',
        3: 'red',
        4: 'blue',
        # inner five nodes, clockwise from top
        5: 'blue',
        6: 'red',
        7: 'red',
        8: 'green',
        9: 'green'
    }

    edges = [
        # outer shape, clockwise from top
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 0),
        # inner shape, clockwise from top
        (5, 0), (5, 7),
        (6, 1), (6, 8),
        (7, 2), (7, 9),
        (8, 3), (8, 5),
        (9, 4), (9, 6)
    ]

    with pychor.LocalBackend(emit_sequence=True) as b:
        coloring = {k: pychor.constant(prover, v) for k, v in coloring.items()}

        print('Running protocol...')
        for i in range(1): #range(len(coloring)**2):
            commitments = commit(prover, verifier, edges, coloring)
            edge, edge_r = challenge(prover, verifier, edges)
            r1, r2 = response(prover, verifier, edge_r, commitments)
            check(prover, verifier, r1, r2)
        print('Done')

run_protocol()
