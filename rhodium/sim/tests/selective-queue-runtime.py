#!/usr/bin/env python3
# Replays mixed native and expanded Queue models against an independent cycle oracle.
# SPDX-License-Identifier: Apache-2.0

import ctypes as c
from pathlib import Path
import random
import os
import subprocess
import sys

build = Path(sys.argv[1])
lib = c.CDLL(str(build / "librhodium_sim.so"))
lib.rds_load.argtypes = [c.c_char_p, c.c_char_p, c.c_size_t]
lib.rds_load.restype = c.c_void_p
lib.rds_free.argtypes = [c.c_void_p]
lib.rds_error.argtypes = [c.c_void_p]
lib.rds_error.restype = c.c_char_p
lib.rds_find_port.argtypes = [c.c_void_p, c.c_char_p]
lib.rds_set_u64.argtypes = [c.c_void_p, c.c_uint32, c.c_uint64]
lib.rds_get_u64.argtypes = [c.c_void_p, c.c_uint32, c.POINTER(c.c_uint64)]
lib.rds_eval.argtypes = [c.c_void_p]
lib.rds_advance.argtypes = [c.c_void_p]
lib.rds_emit_c.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32]
lib.rds_use_compiled.argtypes = [c.c_void_p, c.c_char_p]
output_names = ["input_ready", "output_valid", "output_payload", "occupancy", "phase"]


class Model:
    def __init__(self, name, compiled=False, names=None):
        error = c.create_string_buffer(1024)
        self.ptr = lib.rds_load(str(build / name).encode(), error, len(error))
        assert self.ptr, error.value.decode()
        self.ports = {}
        self.output_names = names or output_names
        if compiled:
            source = build / (name + ".c")
            binary = build / (name + ".so")
            self.check(lib.rds_emit_c(self.ptr, str(source).encode(), 0))
            subprocess.run([os.environ.get("CC", "cc"), "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-fPIC", "-shared", str(source), "-o", str(binary)], check=True)
            self.check(lib.rds_use_compiled(self.ptr, str(binary).encode()))

    def check(self, status):
        assert status == 0, lib.rds_error(self.ptr).decode()

    def port(self, name):
        if name not in self.ports:
            self.ports[name] = lib.rds_find_port(self.ptr, name.encode())
            assert self.ports[name] >= 0, name
        return self.ports[name]

    def set(self, name, value):
        self.check(lib.rds_set_u64(self.ptr, self.port(name), value))

    def outputs(self):
        self.check(lib.rds_eval(self.ptr))
        result = {}
        for name in self.output_names:
            value = c.c_uint64()
            self.check(lib.rds_get_u64(self.ptr, self.port(name), c.byref(value)))
            result[name] = value.value
        return result


for depth in ([] if "--aggregate-only" in sys.argv else [1, 2, 3, 8]):
    for pipe in [False, True]:
        for flow in [False, True]:
            suffix = f"{depth}-{int(pipe)}-{int(flow)}"
            variants = [("direct", False), ("expanded", False)]
            if "--compiled" in sys.argv:
                variants += [("direct", True), ("expanded", True)]
            if "--scalar-optimized" in sys.argv:
                variants += [("optimized", False)]
                if "--compiled" in sys.argv:
                    variants += [("optimized", True)]
            models = [Model(f"{kind}-{suffix}.rds", compiled) for kind, compiled in variants]
            seed = 0xC0FFEE + depth * 4 + pipe * 2 + flow
            random_source = random.Random(seed)
            storage, read, write, count, phase = [0] * depth, 0, 0, 0, 0
            stimuli = []
            for cycle in range(512):
                inputs = dict(payload=random_source.randrange(256), valid=random_source.randrange(4) != 0,
                              ready=random_source.randrange(3) != 0, enable=random_source.randrange(5) != 0,
                              reset=cycle in [0, 1, 37, 113, 255])
                if 2 <= cycle < 2 + depth + 2:
                    inputs.update(valid=True, enable=True, ready=False)
                if 2 + depth + 2 <= cycle < 2 + 2 * depth + 5:
                    inputs.update(valid=True, enable=True, ready=True)
                if 480 <= cycle:
                    inputs.update(valid=False, ready=True)
                if 25 <= cycle <= 37:
                    inputs.update(valid=True, enable=True, ready=False)
                stimuli.append(inputs)
            verilog_outputs = []
            if "--verilator" in sys.argv:
                vectors = "".join(" ".join(str(int(row[name])) for name in ["payload", "valid", "ready", "enable", "reset"]) + "\n" for row in stimuli)
                executable = build / ("verilator-" + suffix) / "VMixedSelective"
                replay = subprocess.run([str(executable)], input=vectors, text=True, capture_output=True, check=True)
                verilog_outputs = [dict(zip(output_names, map(int, line.split()))) for line in replay.stdout.splitlines()]
                assert len(verilog_outputs) == 2 * len(stimuli), replay.stdout
            for cycle, inputs in enumerate(stimuli):
                for model in models:
                    for name, value in inputs.items():
                        model.set(name, value)

                def expected():
                    queue_ready = count < depth or (pipe and inputs["ready"])
                    payload = ((inputs["payload"] + phase) & 255) if flow and count == 0 else storage[read]
                    return dict(input_ready=int(queue_ready and inputs["enable"]),
                                output_valid=int(count > 0 or (flow and inputs["valid"] and inputs["enable"])),
                                output_payload=payload ^ phase, occupancy=count, phase=phase)

                for edge in ["before", "after"]:
                    oracle = expected()
                    for kind, model in zip(variants, models):
                        actual = model.outputs()
                        assert actual == oracle, (suffix, seed, cycle, edge, kind, inputs, actual, oracle)
                        assert model.outputs() == actual, "evaluation changed hardware state"
                    if verilog_outputs:
                        actual = verilog_outputs[2 * cycle + (edge == "after")]
                        assert actual == oracle, (suffix, seed, cycle, edge, "verilator", inputs, actual, oracle)
                    if edge == "after":
                        break
                    queue_ready = count < depth or (pipe and inputs["ready"])
                    enqueue = inputs["valid"] and inputs["enable"] and queue_ready and not (flow and count == 0 and inputs["ready"])
                    dequeue = count > 0 and inputs["ready"]
                    if enqueue:
                        storage[write] = (inputs["payload"] + phase) & 255
                    if inputs["reset"]:
                        count, read, write, phase = 0, 0, 0, 1
                    else:
                        count += int(enqueue) - int(dequeue)
                        read = (read + int(dequeue)) % depth
                        write = (write + int(enqueue)) % depth
                        phase = (phase + 1) & 255
                    for model in models:
                        model.check(lib.rds_advance(model.ptr))
            for model in models:
                lib.rds_free(model.ptr)
if "--aggregate-only" not in sys.argv:
    print("16 mixed Queue configurations passed 512-cycle pre/post-edge replay; compiled=" + str("--compiled" in sys.argv) + "; verilator=" + str("--verilator" in sys.argv) + "; scalar_optimized=" + str("--scalar-optimized" in sys.argv))


if "--twins" in sys.argv:
    names = [lane + suffix for lane in ["first", "second"] for suffix in ["_ingress_out", "_egress_out"]]
    models = [Model("twins-" + kind + ".rds", compiled, names)
              for kind in ["direct", "mixed", "expanded"]
              for compiled in ([False, True] if "--compiled" in sys.argv else [False])]
    states = {lane: dict(storage=[0] * 3, read=0, write=0, count=0) for lane in ["first", "second"]}
    rng = random.Random(782347)
    for cycle in range(256):
        reset = cycle in [0, 1, 67, 129]
        inputs = {}
        for lane in states:
            inputs[lane] = dict(payload=rng.randrange(256), valid=rng.randrange(3) != 0, ready=rng.randrange(2) != 0)
        if 3 <= cycle < 12:
            inputs["first"].update(valid=True, ready=False)
            inputs["second"].update(valid=False, ready=True)
        for model in models:
            model.set("reset", reset)
            for lane, row in inputs.items():
                model.set(lane + "_ingress_in", int(row["valid"]) * 256 + row["payload"])
                model.set(lane + "_egress_in", row["ready"])
        for edge in ["before", "after"]:
            oracle = {}
            for lane, state in states.items():
                oracle[lane + "_ingress_out"] = int(state["count"] < 3)
                oracle[lane + "_egress_out"] = int(state["count"] > 0) * 256 + state["storage"][state["read"]]
            for model in models:
                actual = model.outputs()
                assert actual == oracle, ("twins", cycle, edge, inputs, actual, oracle)
            if edge == "after":
                break
            for lane, state in states.items():
                row = inputs[lane]
                enqueue = row["valid"] and state["count"] < 3
                dequeue = row["ready"] and state["count"] > 0
                if enqueue:
                    state["storage"][state["write"]] = row["payload"]
                if reset:
                    state.update(read=0, write=0, count=0)
                else:
                    state["read"] = (state["read"] + int(dequeue)) % 3
                    state["write"] = (state["write"] + int(enqueue)) % 3
                    state["count"] += int(enqueue) - int(dequeue)
            for model in models:
                model.check(lib.rds_advance(model.ptr))
    for model in models:
        lib.rds_free(model.ptr)
    print("Repeated Queue definitions passed independent direct/mixed/expanded state replay")

if "--aggregate" in sys.argv:
    wide = "--wide" in sys.argv
    payload_width = 65 if wide else 8
    payload_mask = (1 << payload_width) - 1
    word_mask = (1 << 64) - 1
    names = ["input_ready", "output_valid", "left", "right", "occupancy"]
    if wide:
        names += ["left_high", "right_high"]
    for depth in [1, 2, 3, 8]:
        for pipe in [False, True]:
            for flow in [False, True]:
                suffix = f"{depth}-{int(pipe)}-{int(flow)}"
                models = [Model("aggregate-" + kind + "-" + suffix + ".rds", compiled, names)
                          for kind in (["direct", "expanded", "optimized"] if "--optimized" in sys.argv else ["direct", "expanded"])
                          for compiled in ([False, True] if "--compiled" in sys.argv else [False])]
                rng = random.Random(67127 + depth * 4 + pipe * 2 + flow)
                stimuli = []
                for cycle in range(256):
                    row = dict(payload=rng.randrange(1 << payload_width), valid=rng.randrange(3) != 0,
                               ready=rng.randrange(2) != 0, reset=cycle in [0, 1, 37, 113])
                    if cycle == 0 or 2 <= cycle < 2 + depth + 2 or 25 <= cycle <= 37:
                        row.update(valid=True, ready=False)
                    if 2 + depth + 2 <= cycle < 2 + 2 * depth + 5:
                        row.update(valid=True, ready=True)
                    if cycle >= 240:
                        row.update(valid=False, ready=True)
                    if cycle == 255:
                        row.update(valid=True, ready=True)
                    if wide and cycle % 7 == 0:
                        row["payload"] = [0, (1 << 64) - 1, 1 << 64, payload_mask][(cycle // 7) % 4]
                    stimuli.append(row)
                verilog_outputs = []
                if "--verilator" in sys.argv:
                    vectors = "".join(" ".join(str(int(value)) for value in
                        ([row["payload"] & word_mask, row["payload"] >> 64] if wide else [row["payload"]]) +
                        [row["valid"], row["ready"], row["reset"]]) + "\n" for row in stimuli)
                    replay = subprocess.run([str(build / ("verilator-aggregate-" + suffix) / "VAggregateQueue")],
                                            input=vectors, text=True, capture_output=True, check=True)
                    verilog_outputs = [dict(zip(names, map(int, line.split()))) for line in replay.stdout.splitlines()]
                    assert len(verilog_outputs) == 2 * len(stimuli)
                storage, read, write, count = [(0, 0)] * depth, 0, 0, 0
                for cycle, row in enumerate(stimuli):
                    for model in models:
                        for name, value in row.items():
                            if wide and name == "payload":
                                model.set(name, value & word_mask)
                                model.set("payload_high", value >> 64)
                            else:
                                model.set(name, value)
                    for edge in ["before", "after"]:
                        left = row["payload"] if flow and count == 0 else storage[read][0]
                        right = ((left + 1) & payload_mask) if flow and count == 0 else storage[read][1]
                        oracle = dict(input_ready=int(count < depth or (pipe and row["ready"])),
                                      output_valid=int(count > 0 or (flow and row["valid"])),
                                      left=left & word_mask, right=right & word_mask, occupancy=count)
                        if wide:
                            oracle.update(left_high=left >> 64, right_high=right >> 64)
                        for model in models:
                            actual = model.outputs()
                            assert actual == oracle, ("aggregate", suffix, cycle, edge, row, actual, oracle)
                        if verilog_outputs:
                            actual = verilog_outputs[2 * cycle + (edge == "after")]
                            assert actual == oracle, ("aggregate-verilator", suffix, cycle, edge, row, actual, oracle)
                        if edge == "after":
                            break
                        enqueue = row["valid"] and oracle["input_ready"] and not (flow and count == 0 and row["ready"])
                        dequeue = count > 0 and row["ready"]
                        if enqueue:
                            storage[write] = (row["payload"], (left + 1) & payload_mask)
                        if row["reset"]:
                            read, write, count = 0, 0, 0
                        else:
                            read = (read + int(dequeue)) % depth
                            write = (write + int(enqueue)) % depth
                            count += int(enqueue) - int(dequeue)
                        for model in models:
                            model.check(lib.rds_advance(model.ptr))
                for model in models:
                    lib.rds_free(model.ptr)
    print("16 aggregate Queue configurations passed 256-cycle feedback replay; wide=" + str(wide) + "; optimized=" + str("--optimized" in sys.argv))
