#!/usr/bin/env python3
# Verifies failed assertion edges are retryable and publish neither register nor Queue state.
# SPDX-License-Identifier: Apache-2.0
import random
from runtime_model import Model, lib

runs = 0
for depth in [1, 3]:
    for pipe in [False, True]:
        for flow in [False, True]:
            suffix = f"{depth}-{int(pipe)}-{int(flow)}"
            for variant in ["direct", "expanded", "optimized"]:
                for compiled in [False, True]:
                    name = f"{variant}-{suffix}.rds"
                    reference = Model(name)
                    retried = Model(name, compiled)
                    rng = random.Random(31837 + depth * 4 + pipe * 2 + flow)
                    phase = 0
                    rejected = 0
                    for cycle in range(256):
                        reset = cycle in [0, 1, 33, 129]
                        row = dict(payload=rng.randrange(256), valid=rng.randrange(4) != 0,
                                   ready=rng.randrange(3) != 0, reset=reset,
                                   check_enable=cycle % 5 != 0, permit=cycle % 5 != 0)
                        if reset:
                            row.update(permit=False, check_enable=True)
                        if 2 <= cycle < 12 or 25 <= cycle <= 33:
                            row.update(valid=True, ready=False)
                        if 12 <= cycle < 25:
                            row.update(valid=True, ready=True)
                        if cycle >= 240:
                            row.update(valid=False, ready=True)
                        for model in [reference, retried]:
                            for port, value in row.items():
                                model.set(port, value)
                        expected = reference.outputs()
                        assert expected["phase"] == phase, (suffix, variant, cycle, "reference phase")
                        assert retried.outputs() == expected
                        if not reset and cycle % 3 == 0:
                            # Make failed proposals differ from the eventual accepted edge.
                            for port, value in dict(payload=row["payload"] ^ 255, valid=True,
                                                    ready=not row["ready"], permit=False, check_enable=True).items():
                                retried.set(port, value)
                            before = retried.outputs()
                            for attempt in range(2):
                                assert lib.rds_advance(retried.ptr) != 0, (name, compiled, cycle, "accepted failure")
                                message = lib.rds_error(retried.ptr).decode()
                                assert "permit_transfer" in message and f"cycle {cycle}:" in message, message
                                assert retried.outputs() == before, (name, compiled, cycle, "failed edge published state")
                                rejected += 1
                            for port, value in row.items():
                                retried.set(port, value)
                            assert retried.outputs() == expected, (name, compiled, cycle, "failed proposal leaked")
                        reference.check(lib.rds_advance(reference.ptr))
                        retried.check(lib.rds_advance(retried.ptr))
                        phase = 0 if reset else (phase + 1) & 255
                        expected = reference.outputs()
                        assert expected["phase"] == phase
                        assert retried.outputs() == expected, (name, compiled, cycle, "retry differs from clean edge")
                    assert rejected > 100
                    for model in [reference, retried]:
                        lib.rds_free(model.ptr)
                    runs += 1
print(f"{runs} assertion failure/retry traces passed 256 accepted edges; guarded/reset suppression, diagnostics, state atomicity, compiled and optimized execution verified")
