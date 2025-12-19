import pychor
from dataclasses import dataclass
import pandas as pd
import galois

from protocol_beaver import *

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

    def truncate(self, power):
        assert self.power > power, f'Current power {self.power} is not greater than truncation power {power}'
        r1 = p1.constant(GF.Random() * 10**power)
        r2 = p2.constant(GF.Random() * 10**power)
        r1 = p1.constant(GF(2 * 10**self.power))
        r2 = p2.constant(GF(1 * 10**self.power))
        r = SecFp(r1, r2, self.power)
        print(r)

        y = (self + r).reveal()
        z = pychor.locally(lambda y: GF(int(y / 10**power) % p), y)
        result = SecFp(z - r1, z - r2, self.power - power)
        print(result)
        print('y', y)
        print('original', self.reveal(), self.power)
        print('result', result.reveal())
        print(y_truncated)

        1/0

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

# Newton–Raphson for reciprocal
def reciprocal(x, x_reciprocal_guess):
    x_reciprocal = x_reciprocal_guess
    for i in range(3):
        x_reciprocal = ((x * x_reciprocal)*-1 + 2) * x_reciprocal
        # print(x_reciprocal, x_reciprocal.reveal())
        # if x_reciprocal.power > 5:
        #     x_reciprocal = x_reciprocal.truncate(2)
    return x_reciprocal

# if __name__ == '__main__':
#     with pychor.LocalBackend():
#         # P1 knows the input x, and P2 knows the input y
#         x_input = 3.1@p1
#         y_input = 4.2@p2

#         # Create secret shares of the inputs
#         x = SecFp.input_p1(x_input)
#         y = SecFp.input_p2(y_input)

#         for _ in range(20):
#             multiplication_triples.append(deal_triple())

#         r1 = x + y
#         print('x + y:', r1.reveal())

#         r2 = x * y
#         print('x * y:', r2.reveal())

#         r3 = x * y * y
#         print('x * y * y:', r3.reveal())

#         one_half = SecFp.input_p1(0.5@p1)
#         r4 = x * y * y * one_half
#         print('x * y * y / 2:', r4.reveal())

#         two = SecFp.input_p1(2@p1)
#         guess = SecFp.input_p1(0.1@p1)
#         reciprocal_two = reciprocal(two, guess)
#         r5 = x * y * y * reciprocal_two
#         print('x * y * y / 2:', r5.reveal())

@pychor.local_function
def sum_age_heart_disease_patients(df):
    return df[df['target'] == 1]['age'].sum()

@pychor.local_function
def count_heart_disease_patients(df):
    return len(df[df['target'] == 1])

with pychor.LocalBackend():
    for _ in range(20):
        multiplication_triples.append(deal_triple())

    df1 = pychor.locally(pd.read_csv, 'heart1.csv'@p1)
    df2 = pychor.locally(pd.read_csv, 'heart2.csv'@p2)

    # Numerator: compute the total sum of all ages of heart disease patients
    sum1 = SecFp.input_p1(sum_age_heart_disease_patients(df1))
    sum2 = SecFp.input_p2(sum_age_heart_disease_patients(df2))

    total_sum = sum1 + sum2

    # Denominator: compute the total number of heart disease patients
    count_p1 = count_heart_disease_patients(df1)
    count1 = SecFp.input_p1(count_p1)
    count2 = SecFp.input_p2(count_heart_disease_patients(df2))

    total_count = count1 + count2

    guess = SecFp.input_p1(1 / (count_p1 * 2), power=3)
    denominator = reciprocal(total_count, guess)

    average = total_sum * denominator
    print('Average age:', average.reveal())
