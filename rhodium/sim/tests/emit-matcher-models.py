#!/usr/bin/env python3
# Builds prefix-dependent native matcher queries, including legal cross-column feedback.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
from emit_object_models import Fixture


def emit_matcher(directory, rows, columns, feedback=False):
    f = Fixture()
    reset = f.input('reset', 1)
    requests = f.input('requests', rows if feedback else rows * columns)
    accepts = f.input('accepts', columns)
    request_bits = [f.emit(17, 1, [requests], [i]) for i in range(rows if feedback else rows * columns)]
    accept_bits = [f.emit(17, 1, [accepts], [i]) for i in range(columns)]
    if feedback:
        first = f.query(0, rows, request_bits)
        first_bits = [f.emit(17, 1, [first], [i]) for i in range(rows)]
        matrix = [value for i in range(rows) for value in (request_bits[i], first_bits[i])]
        queries = [first, f.query(1, rows, request_bits + first_bits)]
    else:
        matrix = request_bits
        queries = [f.query(col, rows, [matrix[row * columns + earlier]
                                     for earlier in range(col + 1) for row in range(rows)])
                   for col in range(columns)]
    grants = [f.emit(17, 1, [queries[col]], [row])
              for row in range(rows) for col in range(columns)]
    f.output('grants', f.emit(20, rows * columns, grants))
    name = 'matcher-feedback' if feedback else f'matcher-{rows}-{columns}'
    f.save(directory, name, 10, rows, columns, 0, [reset, *matrix, *accept_bits])


def main():
    directory = Path(sys.argv[1])
    for rows, columns in [(1, 1), (3, 2), (3, 5), (8, 4), (11, 11), (64, 2)]:
        emit_matcher(directory, rows, columns)
    emit_matcher(directory, 2, 2, feedback=True)


if __name__ == '__main__':
    main()
