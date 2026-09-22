#!/usr/bin/env python3
# Builds explicit Sv39 TLB ABI fixtures and a host-failure publication variant.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
from emit_object_models import Fixture


def compile_model(path, output, optimize=False):
    command = [os.environ['RDS_OPTIMIZER'], '--input', str(path), '--output', str(output)]
    if not optimize:
        command.append('--no-optimize')
    subprocess.run(command, check=True)


def emit(directory, depth):
    f = Fixture()
    reset = f.input('reset', 1)
    invalidate = f.input('invalidate_all', 1)
    fill = f.input('fill_in', 176)
    inputs = [reset, invalidate]
    inputs.extend(f.emit(17, width, [fill], [low])
                  for low, width in [(175, 1), (1, 1), (123, 27), (2, 53)])
    inputs.extend(f.input(name, width) for name, width in [
        ('virtual_address', 64), ('enabled', 1), ('access', 2),
        ('privilege', 2), ('sum', 1), ('mxr', 1),
        ('probe_virtual_address', 64), ('probe_enabled', 1),
        ('probe_privilege', 2), ('probe_sum', 1), ('probe_mxr', 1)])
    demand = f.query(0, 128, inputs[6:8])
    probe = f.query(5, 128, inputs[12:14])
    for prefix, query in [('', demand), ('probe_', probe)]:
        f.output(prefix + 'hit', f.emit(17, 1, [query], [56]))
        f.output(prefix + 'physical_address', f.emit(17, 56, [query], [0]))
    f.output('fault', f.query(1, 1, inputs[6:12]))
    f.output('probe_fault', f.query(2, 1, inputs[12:17]))
    name = f'tlb-{depth}'
    f.save(directory, name, 11, 81, depth, 0, inputs)
    path = directory / (name + '.json')
    path.with_suffix('.rsim').rename(directory / (name + '-unshared.rsim'))
    compile_model(path, path.with_suffix('.rsim'), optimize=True)
    if depth == 2:
        model = json.loads(path.read_text())
        model['objects'].append([8, 0, 8, 0, [reset] * 5, 'failure-host'])
        host = directory / 'tlb-host.json'
        host.write_text(json.dumps(model))
        compile_model(host, host.with_suffix('.rsim'))


if __name__ == '__main__':
    for depth in (2, 4, 8):
        emit(Path(sys.argv[1]), depth)
