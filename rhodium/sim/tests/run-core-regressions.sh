#!/usr/bin/env bash
# Elaborates ordinary core IR and checks compiler, runtime, and generated-code semantics.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
core_build="${1:-$(mktemp -d "${TMPDIR:-/tmp}/rhodium-core-regressions.XXXXXX")}"
core_build="$(realpath "$core_build")"
cd "$repo_dir"
export RDS_TEST_DIR="$core_build"
export PLTCOMPILEDROOTS="$(mktemp -d "$core_build/compiled.XXXXXX")"
export PYTHONDONTWRITEBYTECODE=1
unset RHODIUM_PRECOMPILED
export RDS_OPTIMIZER="${RDS_OPTIMIZER:-$(bash rhodium/sim/compiler/run.sh --print-path)}"
env PLTCOLLECTS="$repo_dir": "${RACKET:-racket}" -y rhodium/sim/tests/emit-fixtures.rhm
env PLTCOLLECTS="$repo_dir": "${RACKET:-racket}" -y sims/native/tests/contract-test.rhm
runtime_sources=(rhodium/sim/runtime/*.c)
runtime_flags=()
unset RDS_TEST_ASM
if [[ "$("${CC:-cc}" -dumpmachine)" == x86_64*-linux* ]]; then
  runtime_sources+=(rhodium/sim/runtime/set-clear-x86_64.S)
  runtime_flags+=(-DRDS_HAVE_X86_64_ASM)
  export RDS_TEST_ASM=1
fi
"${CC:-cc}" -std=c17 -pthread -O2 -g -Wall -Wextra -Werror -fPIC -shared \
  ${RDS_SANITIZER_FLAGS:-} "${runtime_flags[@]}" "${runtime_sources[@]}" -ldl -o "$core_build/librhodium_sim.so"
for group in compiler semantic runtime codegen inspection; do
  python3 "rhodium/sim/tests/${group}_test.py" "$core_build"
done
printf 'Core regression artifacts: %s\n' "$core_build"
