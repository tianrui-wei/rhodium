#!/usr/bin/env bash
# Builds CIRCT/Verilator counterparts for generated selective Queue fixtures and runs differential replay.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
selective_build="${1:?usage: run-selective-verilator.sh GENERATED_MODEL_DIRECTORY}"
selective_build="$(cd "$selective_build" && pwd)"
circt_opt="${CIRCT_OPT:-$repo_dir/.tools/firtool-1.155.0/bin/circt-opt}"
cd "$repo_dir"
for mlir in "$selective_build"/queue-*.mlir "$selective_build"/aggregate-*.mlir; do
  stem="${mlir##*/}"
  stem="${stem%.mlir}"
  top=MixedSelective
  bench=selective-queue-verilator.cpp
  suffix="${stem#queue-}"
  if [[ "$stem" == aggregate-* ]]; then
    top=AggregateQueue
    bench=aggregate-queue-verilator.cpp
  fi
  verilog="$selective_build/queue-$suffix.sv"
  "$circt_opt" --strip-debuginfo-with-pred='drop-suffix=.mlir' --canonicalize --cse --prettify-verilog \
    --lower-seq-hlmem --lower-seq-firmem --lower-sim-to-sv --lower-verif-to-sv \
    --lower-seq-to-sv='disable-mem-randomization=true disable-reg-randomization=true' \
    --hw-memory-sim='disable-mem-randomization=true disable-reg-randomization=true read-enable-mode=undefined' \
    --sv-mask-non-synthesizable='mode=ifdef macro=SYNTHESIS' --export-verilog "$mlir" -o /dev/null > "$verilog"
  verilator --cc --exe --build --assert -Wno-fatal --top-module "$top" \
    -Mdir "$selective_build/verilator-$suffix" -j 2 "$verilog" \
    "$repo_dir/rhodium/sim/tests/$bench" > "$selective_build/verilator-$suffix.log" 2>&1
done
replay_flags=(--compiled --verilator --aggregate --optimized)
if [[ -f "$selective_build/twins-mixed.rds" ]]; then
  replay_flags+=(--twins)
fi
python3 rhodium/sim/tests/selective-queue-runtime.py "$selective_build" "${replay_flags[@]}"
if [[ -d "$selective_build/nested" ]]; then
  bash "$repo_dir/rhodium/sim/tests/run-selective-verilator.sh" "$selective_build/nested"
fi
