import pychor
import pandas as pd
import numpy as np
from application_beaver import *

@pychor.local_function
def sum_age_heart_disease_patients(df):
    return df[df['target'] == 1]['age'].sum()

@pychor.local_function
def count_heart_disease_patients(df):
    return len(df[df['target'] == 1])

@pychor.local_function
def heart_disease_crosstab(df):
    return tuple(pd.crosstab(df['exang'], df['target']).to_numpy().flatten())

with pychor.LocalBackend():
    for _ in range(20):
        multiplication_triples.append(deal_triple())

    df1 = pychor.locally(pd.read_csv, 'heart1.csv'@p1)
    df2 = pychor.locally(pd.read_csv, 'heart2.csv'@p2)

    crosstab1 = heart_disease_crosstab(df1).untup(4)
    crosstab2 = heart_disease_crosstab(df2).untup(4)

    sec_crosstab1 = [SecInt.input(v) for v in crosstab1]
    sec_crosstab2 = [SecInt.input(v) for v in crosstab2]
    crosstab = [(x + y).reveal() for x, y in zip(sec_crosstab1, sec_crosstab2)]
    crosstab_np = np.array(crosstab).reshape((2,2))
    print('Final crosstab:')
    print(crosstab_np)
