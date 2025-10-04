import pychor
from dataclasses import dataclass
import urllib.request
import galois

GF = galois.GF(2**31-1)
#GF = galois.GF(19)
p1 = pychor.Party('p1')
p2 = pychor.Party('p2')
dealer = pychor.Party('dealer')

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

def f_mult(x_p1, y_p1, x_p2, y_p2, t_p1, t_p2):
    a_p1, b_p1, c_p1 = t_p1
    a_p2, b_p2, c_p2 = t_p2

    d1_p1 = x_p1 - a_p1
    d1_p2 = d1_p1 >> p2
    d2_p2 = x_p2 - a_p2
    d2_p1 = d2_p2 >> p1

    e1_p1 = y_p1 - b_p1
    e1_p2 = e1_p1 >> p2
    e2_p2 = y_p2 - b_p2
    e2_p1 = e2_p2 >> p1

    d_p1 = d1_p1 + d2_p1
    d_p2 = d1_p2 + d2_p2

    e_p1 = e1_p1 + e2_p1
    e_p2 = e1_p2 + e2_p2

    prod_p1 = d_p1 * e_p1 + d_p1 * b_p1 + e_p1 * a_p1 + c_p1
    prod_p2 = d_p2 * b_p2 + e_p2 * a_p2 + c_p2

    return prod_p1, prod_p2

def gen_shares(x):
    s1 = GF.Random()
    s2 = x - s1
    return s1, s2

def deal_shares(x):
    shares = (gen_shares@dealer)(x)
    s1, s2 = shares.untup(2)
    s_p1 = s1 >> p1
    s_p2 = s2 >> p2
    return s_p1, s_p2

def gen_triple():
    a = GF.Random()
    b = GF.Random()
    c = a * b
    return a, b, c

def deal_triple():
    a, b, c = (gen_triple@dealer)().untup(3)
    a_p1, a_p2 = deal_shares(a)
    b_p1, b_p2 = deal_shares(b)
    c_p1, c_p2 = deal_shares(c)
    return (a_p1, b_p1, c_p1), (a_p2, b_p2, c_p2)

def reconstruct(x1, x2):
    return (x1 >> dealer) + (x2 >> dealer)

if __name__ == '__main__':
    with pychor.LocalBackend():
        x = (GF@dealer)(3)
        y = (GF@dealer)(5)
        x_p1, x_p2 = deal_shares(x)
        y_p1, y_p2 = deal_shares(y)
        print('x:', reconstruct(x_p1, x_p2))
        print('y:', reconstruct(y_p1, y_p2))

        t_p1, t_p2 = deal_triple()

        z_p1, z_p2 = f_mult(x_p1, y_p1, x_p2, y_p2, t_p1, t_p2)

        print('x*y:', reconstruct(z_p1, z_p2))
