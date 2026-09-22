#!/usr/bin/env python3
# Builds explicit stateless ALU ABI models for comparison with actual core RTL.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
from compiler_test import OPCODES

for width in (32, 64):
    path = Path(sys.argv[1]) / f'alu-{width}.json'
    model = dict(format='rhodium-simulation-ir-v1', opcodes=OPCODES,
                 values=[width, width, 23, width], operations=[[30, 3, [0, 1, 2], []]],
                 ports=[[0, 0, 'left'], [0, 1, 'right'], [0, 2, 'control'], [1, 3, 'result']],
                 registers=[], objects=[], memories=[], reads=[], writes=[], assertions=[],
                 origins=[], inventory=[], occurrences=[])
    path.write_text(json.dumps(model))
    subprocess.run([os.environ['RDS_OPTIMIZER'], '--input', str(path),
                    '--output', str(path.with_suffix('.rsim')), '--no-optimize'], check=True)
