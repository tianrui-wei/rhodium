#!/usr/bin/env python3
# Checks retained host callback invocation, registered outputs, and preflight failure suppression.
# SPDX-License-Identifier: Apache-2.0
import ctypes as c
import random
from runtime_model import Model, lib, build

Callback = c.CFUNCTYPE(c.c_int, c.c_void_p, c.POINTER(c.c_uint64), c.c_size_t,
                      c.POINTER(c.c_uint64), c.c_size_t)
lib.rds_bind_host.argtypes = [c.c_void_p, c.c_char_p, Callback, c.c_void_p]
mask = (1 << 64) - 1
for variant in ["direct", "optimized"]:
    for compiled in [False, True]:
        model = Model(variant + ".rds", compiled, ["first_result", "second_result", "phase"])
        calls = []
        errors = []
        fail_next = [False]
        failed_calls = []
        @Callback
        def callback(context, inputs, count, outputs, output_count):
            if count != 5 or output_count != 1:
                errors.append((count, output_count))
                return -1
            args = tuple(inputs[i] for i in range(count))
            if fail_next[0]:
                fail_next[0] = False
                failed_calls.append(args)
                outputs[0] = mask
                return -1
            calls.append(args)
            outputs[0] = 0 if args[0] else (args[1] + 3 * args[2]) & mask
            return 0
        for key, value in dict(a=11, b=37, permit=True, reset=False).items():
            model.set(key, value)
        initial = model.outputs()
        names = (build / (variant + ".names")).read_text().splitlines()
        assert len(names) == 2 and len(set(names)) == 2
        # An unbound later sibling must be diagnosed before the earlier callback runs.
        model.check(lib.rds_bind_host(model.ptr, names[0].encode(), callback, None))
        assert lib.rds_advance(model.ptr) != 0
        assert "host callback is not bound" in lib.rds_error(model.ptr).decode()
        assert calls == [] and model.outputs() == initial
        model.check(lib.rds_bind_host(model.ptr, names[1].encode(), callback, None))
        fail_next[0] = True
        assert lib.rds_advance(model.ptr) != 0
        assert "host callback failed" in lib.rds_error(model.ptr).decode()
        assert len(failed_calls) == 1 and calls == []
        assert model.outputs() == initial, "callback failure published tentative outputs"
        phase = 0
        expected = dict(first_result=0, second_result=0, phase=0)
        rng = random.Random(712389)
        for cycle in range(256):
            row = dict(a=rng.getrandbits(64), b=rng.getrandbits(64),
                       reset=cycle in [0, 17, 89], permit=True)
            if row["reset"]:
                row["permit"] = False
            for key, value in row.items():
                model.set(key, value)
            count_before = len(calls)
            for _ in range(3):
                assert model.outputs() == expected
            assert len(calls) == count_before
            if cycle % 5 == 0 and not row["reset"]:
                model.set("permit", False)
                for _ in range(2):
                    assert lib.rds_advance(model.ptr) != 0
                    message = lib.rds_error(model.ptr).decode()
                    assert "permit_host_effect" in message and f"cycle {cycle}:" in message, message
                    assert model.outputs() == expected and len(calls) == count_before
                model.set("permit", True)
            model.check(lib.rds_advance(model.ptr))
            assert not errors, errors
            assert len(calls) == count_before + 2
            expected_args = [(int(row["reset"]), row["a"], row["b"], row["a"], row["b"]),
                             (int(row["reset"]), row["b"], row["a"], row["b"], row["a"])]
            assert sorted(calls[-2:]) == sorted(expected_args), (calls[-2:], expected_args)
            phase = 0 if row["reset"] else (phase + 1) & 255
            expected = dict(first_result=0 if row["reset"] else (row["a"] + 3 * row["b"]) & mask,
                            second_result=0 if row["reset"] else (row["b"] + 3 * row["a"]) & mask, phase=phase)
            assert model.outputs() == expected
        lib.rds_free(model.ptr)
print("4 retained host-effect traces passed 256 edges: two callbacks per accepted edge, none during evaluation or failed preflight; interpreter/generated C and optimization")
