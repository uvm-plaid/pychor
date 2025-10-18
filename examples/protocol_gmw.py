import pychor
from dataclasses import dataclass
import urllib.request
import galois
import protocol_ot

GF_2 = galois.GF(2)

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

def add(a, b):
    return a + b

# Parse a circuit from a Bristol-Fashion specification
def parse_circuit(bristol_fashion_text):
    lines = [l.strip() for l in bristol_fashion_text.split('\n') if l != '']
    total_wires = int(lines[0].split(' ')[1])
    inputs = lines[1]
    outputs = lines[2]
    gates_txt = lines[3:]
    gates = []

    # parse the gates
    for g_txt in gates_txt:
        sp = g_txt.split(' ')
        gate_type = sp[-1]
        if gate_type in ['XOR', 'AND']:
            _, _, in1, in2, out, typ = g_txt.split(' ')
        elif gate_type == 'INV':
            _, _, in1, out, typ = g_txt.split(' ')
            in2 = -1
        else:
            raise RuntimeError('unknown gate type:', gate_type)
        gates.append(Gate(typ, int(in1), int(in2), int(out)))

    ins = inputs.split(' ')
    num_inputs = int(ins[0])

    # generate the bundles of input wires
    w = 0
    input_bundle_sizes = [int(x) for x in inputs.split(' ')[1:]]
    inputs = []
    for bundle_size in ins[1:]:
        inputs.append(list(range(w, w+int(bundle_size))))
        w += int(bundle_size)

    # generate the bundles of output wires
    output_bundle_sizes = [int(x) for x in outputs.split(' ')[1:]]
    total_output_wires = sum(output_bundle_sizes)
    w = total_wires - total_output_wires
    outputs = []
    for bundle_size in output_bundle_sizes:
        outputs.append(list(range(w, w+int(bundle_size))))
        w += int(bundle_size)

    return Circuit(inputs, outputs, gates)

def int_to_bitstring(i, n):
    return [int(x) for x in list(reversed('{0:0b}'.format(i).zfill(n)))]

def bitstring_to_int(bs):
    return sum([int(x)*(2**i) for i, x in enumerate(bs)])

# Compute the value of an AND gate, using all additive shares of its inputs
def S(s1_i, s1_j, s2_i, s2_j):
    return (s1_i + s2_i) * (s1_j + s2_j)

# Generate the truth table describing P2's share of an AND gate's output
def T_G(r, s1_i, s1_j):
    combinations = GF_2([(0,0), (0,1), (1,0), (1,1)])
    output_table = []
    for s2_i, s2_j in combinations:
        s2_k = r + S(s1_i, s1_j, s2_i, s2_j)
        output_table.append(s2_k)
    return output_table

def gmw(p1, p2, p1_inputs, p2_inputs, circuit):
    def gen_shares(inp):
        share1 = GF_2.Random()
        share2 = inp + share1
        return share1, share2

    def share_inputs(p1, p2, p1_wire_vals, p2_wire_vals, inputs, wires):
        for inp, wire in zip(inputs, wires):
            share1, share2 = pychor.locally(gen_shares, inp).untup(2)
            p1_wire_vals[wire] = share1
            share2.send(p1, p2, note='input share')
            p2_wire_vals[wire] = share2

    p1_wire_vals = {}
    p2_wire_vals = {}

    p1_input_wires, p2_input_wires = circuit.inputs

    # secret share inputs
    share_inputs(p1, p2, p1_wire_vals, p2_wire_vals, p1_inputs, p1_input_wires)
    share_inputs(p2, p1, p2_wire_vals, p1_wire_vals, p2_inputs, p2_input_wires)

    # evaluate gates
    for g in circuit.gates:
        in1_p1 = p1_wire_vals[g.in1]
        in2_p1 = p1_wire_vals[g.in2]
        in1_p2 = p2_wire_vals[g.in1]
        in2_p2 = p2_wire_vals[g.in2]

        if g.type == 'XOR':
            p1_wire_vals[g.out] = pychor.locally(add, in1_p1, in2_p1)
            p2_wire_vals[g.out] = pychor.locally(add, in1_p2, in2_p2)
        elif g.type == 'AND':
            p1_out = p1.constant(GF_2.Random())

            table = pychor.locally(T_G, p1_out, in1_p1, in2_p1)
            select_bits = pychor.locally(lambda a,b: [a,b], in1_p2, in2_p2)

            p1_wire_vals[g.out] = p1_out
            p2_wire_vals[g.out] = protocol_ot.ot(p1, p2, select_bits, table)
        else:
            raise Exception('Unknown gate type', g.type)

    # reconstruct outputs
    p1_outputs = []
    p2_outputs = []
    for wire in circuit.outputs[0]:
        share_p1 = p1_wire_vals[wire]
        share_p2 = p2_wire_vals[wire]

        share_p1.send(p1, p2, note='output share')
        share_p2.send(p2, p1, note='output share')
        result = share_p1 + share_p2

        p1_outputs.append(result)
        p2_outputs.append(result)

    return p1_outputs, p2_outputs

def run_gmw(p1, p2):
    with open('adder64.txt', 'r') as f:
        adder_txt = f.read()
    adder = parse_circuit(adder_txt)

    p1_inputs = [p1.constant(x) for x in GF_2(int_to_bitstring(5, 64))]
    p2_inputs = [p2.constant(x) for x in GF_2(int_to_bitstring(6, 64))]

    p1_out, p2_out = gmw(p1, p2, p1_inputs, p2_inputs, adder)
    p1_result = pychor.locally(bitstring_to_int, p1_out)
    p2_result = pychor.locally(bitstring_to_int, p2_out)

    print('RESULTS:')
    print(p1_result)
    print(p2_result)

if __name__ == '__main__':
    p1 = pychor.Party('p1')
    p2 = pychor.Party('p2')

    with pychor.LocalBackend(emit_sequence=True):
        run_gmw(p1, p2)
