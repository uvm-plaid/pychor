import glob
import os
import subprocess
import sys

tests = glob.glob('protocol_*.py')

broken = []
for test in tests:
    print('==================================================')
    print(f'Running test: {test}')
    try:
        subprocess.run(['python3', f'{test}'], check=True)
    except subprocess.CalledProcessError as err:
        print(f'error in python file for {test}!!')
        broken.append(test)
        #sys.exit(err.returncode);

print(f'Broken tests: {broken}')
sys.exit(0)
