"""A private contingency table across two hospitals' patient records.

Two parties each hold half of a heart-disease dataset and want the 2x2
cross-tabulation of exercise-induced angina against diagnosis over the combined
data. Each computes the table for its own records locally -- that part needs no
protocol -- then the four cells are secret-shared with `SecInt` and added, so
the parties learn the combined counts and nothing about each other's rows.

This is the shape most real applications take: do as much as possible in the
clear on local data, and use the secure computation only where the two parties'
data actually has to meet.
"""

import pychor
from pathlib import Path
import pandas as pd
import numpy as np
from application_beaver import *
from example_backend import backend, check

DATA_DIR = Path(__file__).resolve().parent

@pychor.local_function
def heart_disease_crosstab(df):
    return tuple(pd.crosstab(df['exang'], df['target']).to_numpy().flatten())


def main():
    with backend(parties=[p1, p2, dealer]):
        multiplication_triples.clear()
        for _ in range(20):
            multiplication_triples.append(deal_triple())

        df1 = pychor.locally(pd.read_csv, str(DATA_DIR / 'heart1.csv')@p1)
        df2 = pychor.locally(pd.read_csv, str(DATA_DIR / 'heart2.csv')@p2)

        crosstab1 = heart_disease_crosstab(df1).untup(4)
        crosstab2 = heart_disease_crosstab(df2).untup(4)

        sec_crosstab1 = [SecInt.input(v) for v in crosstab1]
        sec_crosstab2 = [SecInt.input(v) for v in crosstab2]
        crosstab = [(x + y).reveal() for x, y in zip(sec_crosstab1, sec_crosstab2)]
        crosstab_np = np.array(crosstab).reshape((2, 2))
        print('Final crosstab:')
        print(crosstab_np)

        # Verified against the same cross-tabulation computed in the clear over
        # both CSVs together.
        expected = [39, 95, 49, 17]
        for cell, value in zip(crosstab, expected):
            check(cell, value, f'crosstab cell {value}')
        return crosstab


if __name__ == '__main__':
    main()
