#!/usr/bin/env bash
# Builds and replays retained Queue models using fresh bytecode and external generated artifacts.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
selective_build="$(mktemp -d /tmp/rhodium-selective-test.XXXXXX)"
selective_compiled="$(mktemp -d /tmp/rhodium-selective-compiled.XXXXXX)"
cd "$repo_dir"
export RDS_TEST_DIR="$selective_build"
export RDS_NESTED_DIR="$selective_build/nested"
export RDS_MAP_DIR="$selective_build/mapped"
export RDS_NESTED_MAP_DIR="$selective_build/nested-map"
export RDS_WIDE_DIR="$selective_build/wide"
export RDS_VECTOR_DIR="$selective_build/vector"
mkdir "$RDS_NESTED_DIR" "$RDS_MAP_DIR" "$RDS_VECTOR_DIR" "$RDS_WIDE_DIR" "$RDS_NESTED_MAP_DIR"
touch "$RDS_WIDE_DIR/wide-payload" "$RDS_NESTED_MAP_DIR/wide-payload"
export PLTCOMPILEDROOTS="$selective_compiled"
unset RHODIUM_PRECOMPILED
tools/run-racket-tests.sh rhodium/sim/tests/*-test.rhm
"${CC:-cc}" -std=c17 -pthread -O2 -Wall -Wextra -Werror -fPIC -shared \
  rhodium/sim/runtime/*.c -ldl -o "$selective_build/librhodium_sim.so"
python3 rhodium/sim/tests/selective-queue-runtime.py "$selective_build" --compiled --twins --aggregate --optimized
cp "$selective_build/librhodium_sim.so" "$RDS_NESTED_DIR/"
python3 rhodium/sim/tests/selective-queue-runtime.py "$RDS_NESTED_DIR" --compiled --aggregate --optimized --twins
cp "$selective_build/librhodium_sim.so" "$RDS_MAP_DIR/"
python3 rhodium/sim/tests/selective-queue-runtime.py "$RDS_MAP_DIR" --compiled --scalar-optimized --aggregate --optimized
cp "$selective_build/librhodium_sim.so" "$RDS_VECTOR_DIR/"
python3 rhodium/sim/tests/selective-queue-runtime.py "$RDS_VECTOR_DIR" --compiled --aggregate --optimized --aggregate-only
cp "$selective_build/librhodium_sim.so" "$RDS_WIDE_DIR/"
python3 rhodium/sim/tests/selective-queue-runtime.py "$RDS_WIDE_DIR" --compiled --aggregate --optimized --aggregate-only --wide
cp "$selective_build/librhodium_sim.so" "$RDS_NESTED_MAP_DIR/"
python3 rhodium/sim/tests/selective-queue-runtime.py "$RDS_NESTED_MAP_DIR" --compiled --aggregate --optimized --aggregate-only --wide
printf 'Generated artifacts: %s\n' "$selective_build"
