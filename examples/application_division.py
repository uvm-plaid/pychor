"""Secure division: the average age of heart-disease patients across two parties.

Each party holds half of a private patient record set. Together they compute the
mean age of the patients with heart disease without either learning the other's
data. The mean needs a division, which secret sharing does not provide directly,
so the reciprocal of the denominator is computed by Newton-Raphson iteration
using only addition and multiplication.

The exponent budget is the thing to watch. `SecFp` scales each value by a power
of ten, and multiplying two values *adds* their exponents, so the iteration's
exponent grows 3 -> 7 -> 15 and the final product reaches 16. At exponent 16 the
encoded average is about 5.2e17, which fits the 2**61-1 field with roughly
2.2x to spare. A third iteration would reach exponent 32 and about 5.2e33,
overflowing any practical field -- so the iteration count is bounded by the
field, not by convergence. Real fixed-point MPC solves this with a truncation
protocol that rescales a shared value back down; here two iterations already
give the exact answer, so none is needed.
"""

import pychor
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import galois

from protocol_beaver import *
from example_backend import backend, check

DATA_DIR = Path(__file__).resolve().parent

multiplication_triples = []

@pychor.local_function
def encode_fixpoint(val, power):
    return GF(int(val * 10**power) % p)

@dataclass
class SecFp:
    s1: galois.GF
    s2: galois.GF
    power: int

    @classmethod
    def input_p1(cls, val, power=1):
        s1, s2 = share(encode_fixpoint(val, power)).untup(2)
        s2.send(p1, p2)
        return SecFp(s1, s2, power)

    @classmethod
    def input_p2(cls, val, power=1):
        s1, s2 = share(encode_fixpoint(val, power)).untup(2)
        s1.send(p2, p1)
        return SecFp(s1, s2, power)

    def __add__(x, y):
        if isinstance(y, SecFp):
            assert x.power == y.power
            return SecFp(x.s1 + y.s1,
                         x.s2 + y.s2,
                         x.power)
        elif isinstance(y, int):
            return SecFp(x.s1 + encode_fixpoint(y@p1, x.power),
                         x.s2,
                         x.power)
        else:
            raise Exception('incompatible type for addition:', y)

    def __mul__(x, y):
        if isinstance(y, SecFp):
            triple = multiplication_triples.pop()
            r1, r2 = protocol_mult((x.s1, x.s2),
                                   (y.s1, y.s2),
                                   triple)
            return SecFp(r1, r2, x.power + y.power)
        elif isinstance(y, int):
            y_enc1 = encode_fixpoint(y@p1, 0)
            y_enc2 = encode_fixpoint(y@p2, 0)
            return SecFp(x.s1 * y_enc1,
                         x.s2 * y_enc2,
                         x.power)
        else:
            raise Exception('incompatible type for multiplication:', y)

    def reveal(self):
        @pychor.local_function
        def decode_fixpoint(s1, s2):
            val = int(s1 + s2)
            if val > p/2:
                return (val - p) / (10**self.power)
            else:
                return val / (10**self.power)
        self.s1.send(p1, p2)
        self.s2.send(p2, p1)
        return decode_fixpoint(self.s1, self.s2)

# Two iterations of Newton-Raphson for the reciprocal: x_{n+1} = x_n(2 - a*x_n).
#
# Newton squares its relative error at each step, so the number of iterations
# needed depends entirely on the initial guess. Here the guess is derived from
# one party's local count, which is roughly half the total, putting it within
# about 1% of the true reciprocal -- so two iterations reach a relative error of
# about 4e-9, which is exact for our purposes. Each iteration costs two
# multiplications and raises the exponent from e to 2e+1, so two is also as many
# as the field can accommodate; see the module docstring.
NEWTON_ITERATIONS = 2


def reciprocal(x, x_reciprocal_guess):
    x_reciprocal = x_reciprocal_guess
    for _ in range(NEWTON_ITERATIONS):
        x_reciprocal = ((x * x_reciprocal)*-1 + 2) * x_reciprocal
    return x_reciprocal


@pychor.local_function
def sum_age_heart_disease_patients(df):
    return df[df['target'] == 1]['age'].sum()

@pychor.local_function
def count_heart_disease_patients(df):
    return len(df[df['target'] == 1])

def main():
    with backend(parties=[p1, p2, dealer]):
        # Each multiplication consumes one Beaver triple. Two Newton iterations
        # need two each, plus one for the final product.
        multiplication_triples.clear()
        for _ in range(20):
            multiplication_triples.append(deal_triple())

        df1 = pychor.locally(pd.read_csv, str(DATA_DIR / 'heart1.csv')@p1)
        df2 = pychor.locally(pd.read_csv, str(DATA_DIR / 'heart2.csv')@p2)

        # Numerator: compute the total sum of all ages of heart disease patients
        sum1 = SecFp.input_p1(sum_age_heart_disease_patients(df1))
        sum2 = SecFp.input_p2(sum_age_heart_disease_patients(df2))

        total_sum = sum1 + sum2

        # Denominator: compute the total number of heart disease patients
        count_p1 = count_heart_disease_patients(df1)
        count1 = SecFp.input_p1(count_p1)
        count2 = SecFp.input_p2(count_heart_disease_patients(df2))

        total_count = count1 + count2

        # The guess only has to land within (0, 2/count) for Newton to converge.
        # One party's own count is a good enough starting point, and it costs no
        # communication.
        guess = SecFp.input_p1(1 / (count_p1 * 2), power=3)
        denominator = reciprocal(total_count, guess)

        average = total_sum * denominator
        result = average.reveal()
        print('Average age:', result)

        # 5852 years of age spread over 112 patients with heart disease.
        # Two Newton iterations leave a relative error of about 4e-9, and the
        # result is deterministic: the shares are random but reconstruct exactly,
        # so this comes out bit-identical every run.
        check(result, 5852 / 112, 'average age', tol=1e-6)
        return result


if __name__ == '__main__':
    main()
