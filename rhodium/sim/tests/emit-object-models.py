#!/usr/bin/env python3
# Builds explicit native object ABI fixtures without elaborating or recognizing library bodies.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
from compiler_test import OPCODES

NONE = 0xffffffff


class Fixture:
    def __init__(self):
        self.widths, self.ops, self.ports = [], [], []

    def input(self, name, width):
        value = len(self.widths)
        self.widths.append(width)
        self.ports.append([0, value, name])
        return value

    def emit(self, code, width, args=(), immediates=()):
        value = len(self.widths)
        self.widths.append(width)
        self.ops.append([code, value, list(args), list(immediates)])
        return value

    def query(self, index, width, args=()):
        return self.emit(29, width, args, [0, index])

    def output(self, name, value):
        self.ports.append([1, value, name])

    def channel_input(self, name, width):
        packed = self.input(name, width + 1)
        valid = self.emit(17, 1, [packed], [width])
        data = self.emit(17, width, [packed], [0]) if width else NONE
        return valid, data

    def channel_output(self, name, width, valid, data):
        value = self.emit(20, width + 1, [data, valid]) if width else valid
        self.output(name, value)

    def save(self, directory, name, kind, width, depth, flags, inputs):
        model = dict(format='rhodium-simulation-ir-v1', opcodes=OPCODES,
                     values=self.widths, operations=self.ops, ports=self.ports,
                     objects=[[kind, width, depth, flags, inputs, name]],
                     registers=[], memories=[], reads=[], writes=[], assertions=[],
                     origins=[], inventory=[], occurrences=[])
        path = directory / (name + '.json')
        path.write_text(json.dumps(model))
        subprocess.run([os.environ['RDS_OPTIMIZER'], '--input', str(path),
                        '--output', str(path.with_suffix('.rsim')), '--no-optimize'], check=True)


def channel(directory, name, kind, width, depth, flags, tokens):
    f = Fixture()
    reset = f.input('reset', 1)
    valid, data = f.channel_input('update_in' if kind == 3 else 'ingress_in', width)
    ready = NONE if flags & 8 else f.input('egress_in', 1)
    inputs = [reset, valid, NONE if tokens else data, ready]
    if kind == 1:
        f.output('count', f.query(0, depth.bit_length()))
        f.output('ingress_out', f.query(1, 1, [ready] if flags & 2 else []))
    payload = f.query(3, width, [data] if kind == 1 and flags & 4 and not tokens else [])
    available = f.query(2, 1, [valid] if kind == 1 and flags & 4 else [])
    f.channel_output('egress_out', width, available, payload)
    f.save(directory, name + ('-tokens' if tokens else ''), kind, width, depth,
           flags | int(tokens), inputs)


def broadcast(directory, width, tokens):
    f = Fixture()
    reset = f.input('reset', 1)
    valid, data = f.channel_input('ingress_in', width)
    ready = [f.input(f'egress_{i}_in', 1) for i in range(3)]
    f.output('ingress_out', f.query(0, 1, ready))
    payload = f.query(1, width) if width else NONE
    for i in range(3):
        f.channel_output(f'egress_{i}_out', width, f.query(2 + i, 1), payload)
    name = 'broadcast' if width else 'ctrl-broadcast'
    f.save(directory, name + ('-tokens' if tokens else ''), 9, width, 3,
           int(tokens), [reset, valid, NONE if tokens else data, *ready])


def arbiter(directory, packet, tokens):
    f = Fixture()
    inputs = [f.input('reset', 1), f.input('egress_in', 1)]
    requests, payloads = [], []
    for i in range(3):
        valid, data = f.channel_input(f'ingress_{i}_in', 8)
        requests.append(valid)
        payloads.append(data)
        inputs.extend([valid, NONE if tokens else data])
    if packet:
        ends = f.input('ends_packet', 3)
        inputs.extend(f.emit(17, 1, [ends], [i]) for i in range(3))
    f.output('chosen', f.query(0, 2, requests))
    f.channel_output('egress_out', 8, f.query(1, 1, requests),
                     f.query(2, 8, [] if tokens else requests + payloads))
    for i in range(3):
        f.output(f'ingress_{i}_out', f.query(3 + i, 1, requests + [inputs[1]]))
    name = 'packet-rr' if packet else 'rr'
    f.save(directory, name + ('-tokens' if tokens else ''), 6, 8, 3,
           2 | (16 if packet else 0) | int(tokens), inputs)


def main():
    directory = Path(sys.argv[1])
    for tokens in (False, True):
        for width in (8, 65, 4096):
            for depth in (1, 3, 1024):
                for pipe in (0, 1):
                    for flow in (0, 1):
                        channel(directory, f'fifo-{width}-{depth}-{pipe}{flow}',
                                1, width, depth, pipe * 2 + flow * 4, tokens)
        channel(directory, 'offer', 3, 65, 1, 0, tokens)
        channel(directory, 'valid-pipe', 2, 65, 3, 8, tokens)
        broadcast(directory, 65, tokens)
        broadcast(directory, 0, tokens)
        arbiter(directory, False, tokens)
        arbiter(directory, True, tokens)


if __name__ == '__main__':
    main()
