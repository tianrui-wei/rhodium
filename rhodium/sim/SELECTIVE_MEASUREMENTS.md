<!-- Records reviewed measurements of identical retained-native and expanded Queue circuits. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Selective lowering measurements

Direct Queue selection produces smaller execution images and reduces lowering
time for the depth-three/eight cases below. Compiled checked throughput is
similar overall; expanded depth-one RTL is faster. Peak batch memory is nearly
unchanged. These results establish neither a universal native speedup nor a
whole-SoC performance result.

## Workload and reproduction

Measured source: `a6ab8c732e3f43349502bf96a46c49134d9880f5`, with a clean worktree.
The existing `MixedSelective` fixture connects an eight-bit Queue to ordinary
arithmetic, control gating, and a clocked phase register. Each configuration has
three repetitions, with one million cycles in both interpreter and generated-C
execution. All 72 executions check every output before and after each edge
against an independent oracle. Checksums agree across implementations and
repetitions; each configuration's model hash is stable across repetitions.
Direct selection expands zero Queue bodies; fallback expands exactly one.

The host was an AMD Ryzen 7 7800X3D, pinned to logical CPU 6, with GCC 16.2.1
(`-std=c17 -O2 -Wall -Wextra -Werror`), Racket 9.3 CS, and Rhombus package checksum
`17d043235da8abc8d677c63b65034032dbb60b42`. The selected CPU and its sibling were
idle when sampled; other machine activity was not controlled. Measurements were
recorded on 2026-09-22. Reproduce with the documented dependency setup:

```sh
python3 rhodium/sim/tests/benchmark-selective.py /path/to/artifacts --cpu 6
```

Choose an available CPU on the local host. The runner creates fresh bytecode,
warms both paths until a complete pair leaves the compiled root unchanged, and
rejects bytecode changes during measured emission. An initial run exposed
transitive dependency rebuilding; its process-time/RSS samples were discarded.
The final run continued that same validation batch with `--resume`, preserved
the earlier artifacts, and verified all 1,848 cached files remained unchanged.
Direct/expanded emission order alternates across repetitions. Garbage collection
precedes each circuit's timed phases. Racket startup is excluded from circuit
phase timings and included in the separately reported batch process metrics.

## Median circuit and compilation measurements

Every paired entry is **direct / expanded**. Options `00` disable both pipe and
flow; `11` enable replacement and empty bypass. Sizes are bytes. C emission and
compilation are separate from elaboration and simulation-model lowering.

| Depth/options | Elaboration ms | Lowering ms | C emission ms | C compilation ms |
|---|---:|---:|---:|---:|
| 1/00 | 0.940 / 0.950 | 6.582 / 6.516 | 1.74 / 1.82 | 260.4 / 251.7 |
| 1/11 | 0.963 / 0.926 | 5.445 / 6.244 | 1.84 / 1.91 | 250.9 / 246.0 |
| 3/00 | 0.865 / 0.886 | 4.391 / 7.663 | 1.64 / 1.86 | 250.0 / 250.3 |
| 3/11 | 0.855 / 0.861 | 4.075 / 7.765 | 1.63 / 1.79 | 249.1 / 251.7 |
| 8/00 | 0.839 / 0.864 | 3.971 / 7.521 | 1.81 / 1.72 | 249.8 / 250.8 |
| 8/11 | 0.877 / 0.871 | 4.747 / 7.417 | 1.77 / 1.75 | 250.0 / 252.9 |

| Depth/options | Model bytes | Generated C bytes | Shared library bytes |
|---|---:|---:|---:|
| 1/00 | 792 / 876 | 15,829 / 13,945 | 16,200 / 16,096 |
| 1/11 | 804 / 1,100 | 15,158 / 14,644 | 16,120 / 16,128 |
| 3/00 | 792 / 1,682 | 16,405 / 18,033 | 16,200 / 16,352 |
| 3/11 | 804 / 1,906 | 15,757 / 18,695 | 16,120 / 16,352 |
| 8/00 | 792 / 1,718 | 16,405 / 18,062 | 16,200 / 16,352 |
| 8/11 | 804 / 1,942 | 15,757 / 18,724 | 16,120 / 16,352 |

## Checked execution and peak memory

Throughput is millions of checked cycles per second, including host stimulus,
the independent oracle, and all pre/post-edge port accesses. It is not isolated
kernel throughput. Values are medians of three samples using identical seeds.

| Depth/options | Interpreter direct / expanded | Compiled direct / expanded |
|---|---:|---:|
| 1/00 | 3.989 / 4.974 | 6.924 / 7.271 |
| 1/11 | 3.909 / 4.535 | 6.971 / 7.081 |
| 3/00 | 3.945 / 3.967 | 6.899 / 6.958 |
| 3/11 | 3.880 / 3.654 | 6.844 / 6.835 |
| 8/00 | 3.942 / 3.958 | 6.915 / 7.003 |
| 8/11 | 3.870 / 3.639 | 6.869 / 6.910 |

Each emission process covers all six circuits for one mode and repetition.
Its direct/expanded median wall time was 0.733/0.749 seconds. Peak RSS was
262.34/262.60 MiB; ranges were 262.34–262.91 and 262.36–264.20 MiB. These are
whole-process peaks including startup, not individual circuit allocations.
C-compilation peak RSS ranged from 125.73 to 127.31 MiB; emission and execution
process peaks were 23.80 MiB, including their common launch/runtime footprint.
The data does not establish a meaningful peak-memory advantage.

The external `report.json` contains all 36 model samples, six batch measurements,
source hashes, tool metadata, and warmup evidence. Its SHA-256 is
`53d62091cf9dbf0b4d49bcc5dfec385dde479f2f0cb24a9c7b2a87924028c917`.
Raw logs, generated models/C/libraries, and the report remain outside version
control. The [development guide](DEVELOPING.md#retained-versus-expanded-measurement)
owns the measurement workflow and its scope.
