#!/usr/bin/env bash
# Builds and replays retained Queue models using fresh bytecode and external generated artifacts.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
selective_build="$(mktemp -d /tmp/rhodium-selective-test.XXXXXX)"
selective_compiled="$(mktemp -d /tmp/rhodium-selective-compiled.XXXXXX)"
cd "$repo_dir"
export RDS_TEST_DIR="$selective_build"
export PLTCOMPILEDROOTS="$selective_compiled"
unset RHODIUM_PRECOMPILED
tools/run-racket-tests.sh rhodium/sim/tests/*-test.rhm
"${CC:-cc}" -std=c17 -pthread -O2 -Wall -Wextra -Werror -fPIC -shared \
  rhodium/sim/runtime/*.c -ldl -o "$selective_build/librhodium_sim.so"
python3 rhodium/sim/tests/selective-queue-runtime.py "$selective_build" --compiled --twins --aggregate --optimized
printf 'Generated artifacts: %s\n' "$selective_build"
