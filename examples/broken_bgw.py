import pychor
from dataclasses import dataclass
import urllib.request
import galois
import shamir
import protocol_mult

@dataclass
class Gate:
    type: str
    in1: int
    in2: int
    out: int

@dataclass
class Circuit:
    inputs: any
    outputs: any
    gates: any

def gen_prod_ish_circuit(input_wires):
    wire_num = len(input_wires)
    output_wire = input_wires[0]

    gates = []
    for w in input_wires[1:]:
        gates.append(Gate('MUL', w, output_wire, wire_num))
        mul_wire = wire_num
        wire_num += 1
        gates.append(Gate('ADD', w, mul_wire, wire_num))
        output_wire = wire_num
        wire_num += 1

    outputs = [output_wire]
    return Circuit(input_wires, outputs, gates)

def bgw(parties, inputs, circuit):

    # init wires
    wire_vals = {p: {} for p in parties}

    # share inputs
    for p in parties:
        wire, val = inputs[p]
        shares = (shamir.share@p)(val, len(parties)//2, len(parties))

        for dest, share in zip(parties, shares.unlist(len(parties))):
            wire_vals[dest][wire] = share.with_note('input share') >> dest

    # evaluate gates
    for g in circuit.gates:
        if g.type == 'ADD':
            for p in parties:
                wire_vals[p][g.out] = (shamir.add@p)(wire_vals[p][g.in1],
                                                     wire_vals[p][g.in2])
        elif g.type == 'MUL':
            in1_shares = {p: wire_vals[p][g.in1] for p in parties}
            in2_shares = {p: wire_vals[p][g.in2] for p in parties}
            results = protocol_mult.f_mult(parties, in1_shares, in2_shares)

            for p in parties:
                wire_vals[p][g.out] = results[p]
        else:
            raise Exception('Unknown gate type', g.type)

    # reconstruct outputs
    outputs = {p: [] for p in parties}

    for wire in circuit.outputs:
        shares = [wire_vals[p][wire] for p in parties]
        collected_shares = {p: [share.with_note('output share') >> p for share in shares] for p in parties}

        for p in parties:
            val = (shamir.reconstruct@p)(collected_shares[p])
            outputs[p].append(val)

    return outputs



if __name__ == '__main__':
    parties = [pychor.Party(f'p{i}') for i in range(6)]
    with pychor.LocalBackend(emit_sequence=True):
        inputs = {p: 2 for p in parties}
        input_wires = {p: w for p, w in zip(parties, range(len(parties)))}
        circuit = gen_prod_ish_circuit(list(input_wires.values()))
        input_pairs = {p: (input_wires[p], pychor.constant(p, inputs[p])) for p in parties}

        results = bgw(parties, input_pairs, circuit)

        print('RESULTS:')
        print(results)
