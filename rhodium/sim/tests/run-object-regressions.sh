#!/usr/bin/env bash
# Compares native object ABI fixtures with independent protocol oracles and actual Flow RTL.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
object_build="${1:-$(mktemp -d "${TMPDIR:-/tmp}/rhodium-object-regressions.XXXXXX")}"
object_build="$(realpath "$object_build")"
cd "$repo_dir"
export RDS_TEST_DIR="$object_build"
export PLTCOMPILEDROOTS="$(mktemp -d "$object_build/compiled.XXXXXX")"
export PYTHONDONTWRITEBYTECODE=1
unset RHODIUM_PRECOMPILED
export RDS_OPTIMIZER="${RDS_OPTIMIZER:-$(bash rhodium/sim/compiler/run.sh --print-path)}"
tools/run-racket-tests.sh rhodium/sim/tests/emit-object-rtl.rhm rhodium/sim/tests/emit-replication.rhm rhodium/sim/tests/emit-library.rhm rhodium/sim/tests/emit-matcher.rhm rhodium/sim/tests/native-query-test.rhm rhodium/sim/tests/emit-alu.rhm
python3 rhodium/sim/tests/emit_object_models.py "$object_build"
python3 rhodium/sim/tests/emit-matcher-models.py "$object_build"
python3 rhodium/sim/tests/emit-alu-models.py "$object_build"
runtime_sources=(rhodium/sim/runtime/*.c)
runtime_flags=()
unset RDS_TEST_ASM
if [[ "$("${CC:-cc}" -dumpmachine)" == x86_64*-linux* ]]; then
  runtime_sources+=(rhodium/sim/runtime/set-clear-x86_64.S)
  runtime_flags+=(-DRDS_HAVE_X86_64_ASM)
  export RDS_TEST_ASM=1
fi
"${CC:-cc}" -std=c17 -pthread -O2 -g -Wall -Wextra -Werror -fPIC -shared \
  ${RDS_SANITIZER_FLAGS:-} "${runtime_flags[@]}" "${runtime_sources[@]}" -ldl -o "$object_build/librhodium_sim.so"
RDS_TEST_COMPILED= python3 rhodium/sim/tests/native_objects_test.py "$object_build"
RDS_TEST_COMPILED=1 python3 rhodium/sim/tests/native_objects_test.py "$object_build"
python3 rhodium/sim/tests/library_test.py "$object_build"
python3 rhodium/sim/tests/matcher_test.py "$object_build"
python3 rhodium/sim/tests/alu_test.py "$object_build"
printf 'Object regression artifacts: %s\n' "$object_build"
