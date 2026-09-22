#!/usr/bin/env python3
# Replays mixed Queue/pipe implementations against an independent simultaneous-edge oracle.
# SPDX-License-Identifier: Apache-2.0
import random
import subprocess
import sys
from runtime_model import Model, lib, build

names = ["input_ready", "output_valid", "output_payload", "occupancy"]
configurations = 0
for kind in ["elastic", "control", "valid", "always"]:
    for stages in [1, 2, 4]:
        for flushable in ([False, True] if kind in ["valid", "always"] else [False]):
            suffix = f"{kind}-{stages}-{int(flushable)}"
            models = [Model(f"{variant}-{suffix}.rds", compiled, names)
                      for variant in ["direct", "expanded", "optimized"]
                      for compiled in [False, True]]
            rng = random.Random(12673 + stages * 2 + flushable)
            stimuli = []
            for cycle in range(512):
                row = dict(payload=rng.randrange(256), valid=rng.randrange(4) != 0,
                           ready=rng.randrange(3) != 0, flush=cycle in [19, 20, 64, 193],
                           reset=cycle in [0, 1, 37, 255])
                if 2 <= cycle < 14 or 25 <= cycle <= 37:
                    row.update(valid=True, ready=False)
                if 14 <= cycle < 25:
                    row.update(valid=True, ready=True)
                if cycle >= 490:
                    row.update(valid=False, ready=True)
                stimuli.append(row)
            observed = []
            if "--verilator" in sys.argv:
                vectors = "".join(" ".join(str(int(row[name])) for name in
                    ["payload", "valid", "ready", "flush", "reset"]) + "\n" for row in stimuli)
                result = subprocess.run([str(build / ("verilator-pipe-" + suffix) / "VMixedPipe")],
                                        input=vectors, text=True, capture_output=True, check=True)
                observed = [dict(zip(names, map(int, line.split()))) for line in result.stdout.splitlines()]
                assert len(observed) == 2 * len(stimuli)
            storage, read, write, count = [0] * 3, 0, 0, 0
            valid, payload = [False] * stages, [0] * stages
            for cycle, row in enumerate(stimuli):
                for model in models:
                    for name, value in row.items():
                        model.set(name, value)
                for edge in [0, 1]:
                    readiness = [True] * (stages + 1)
                    if kind in ["elastic", "control"]:
                        readiness[-1] = row["ready"]
                        for i in reversed(range(stages)):
                            readiness[i] = not valid[i] or readiness[i + 1]
                    queue_valid = count > 0 or row["valid"]
                    queue_bits = storage[read] if count else row["payload"]
                    queue_ready = count < 3 or readiness[0]
                    expected = dict(input_ready=int(queue_ready), output_valid=int(valid[-1]),
                                    output_payload=0 if kind == "control" else payload[-1], occupancy=count)
                    for model in models:
                        assert model.outputs() == expected, (suffix, cycle, edge, row, model.outputs(), expected)
                        assert model.outputs() == expected, (suffix, "repeated evaluation changed state")
                    if observed:
                        assert observed[2 * cycle + edge] == expected, (suffix, cycle, edge, observed[2 * cycle + edge], expected)
                    if edge:
                        break
                    upstream_valid = [queue_valid] + valid[:-1]
                    upstream_payload = [queue_bits] + payload[:-1]
                    for i in range(stages):
                        advances = readiness[i] if kind in ["elastic", "control"] else True
                        captures = advances and (upstream_valid[i] or kind == "always")
                        if captures:
                            payload[i] = upstream_payload[i]
                        if advances:
                            valid[i] = upstream_valid[i]
                    if row["reset"] or (flushable and row["flush"]):
                        valid = [False] * stages
                    enqueue = row["valid"] and queue_ready and not (count == 0 and readiness[0])
                    dequeue = count > 0 and readiness[0]
                    if enqueue:
                        storage[write] = row["payload"]
                    if row["reset"]:
                        read, write, count = 0, 0, 0
                    else:
                        read = (read + int(dequeue)) % 3
                        write = (write + int(enqueue)) % 3
                        count += int(enqueue) - int(dequeue)
                    for model in models:
                        model.check(lib.rds_advance(model.ptr))
            for model in models:
                lib.rds_free(model.ptr)
            configurations += 1
print(f"{configurations} mixed Queue/pipe configurations passed 512-cycle replay; optimized=True; compiled=True; verilator={'--verilator' in sys.argv}")
