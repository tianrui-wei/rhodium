#!/usr/bin/env python3
# Loads native test models and runs interpreter or generated-C execution through one checked ABI.
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


