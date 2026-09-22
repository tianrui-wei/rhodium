#!/usr/bin/env bash
# Builds and validates external semantic specialization against the native runtime.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
build_dir="$(realpath "${1:?supply directory containing librhodium_sim.so}")"
cd "$repo_dir"
compiler_sources=()
for unit in model semantic snapshot passes fifo-width fifo-derived bit-relations selectors regroup flow contracts payloads lifetimes transport; do
  object="$build_dir/specialization-$unit.o"
  "${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror \
    -c "rhodium/sim/compiler/$unit.cpp" -o "$object"
  compiler_sources+=("$object")
done
"${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror sims/native/specialize-empty.cpp \
  "${compiler_sources[@]}" -o "$build_dir/specialize-empty"
"${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror sims/native/tests/empty_specialization_test.cpp \
  "${compiler_sources[@]}" -L"$build_dir" -lrhodium_sim -Wl,-rpath,"$build_dir" \
  -o "$build_dir/empty-specialization-test"
"$build_dir/empty-specialization-test" "$build_dir/empty-specialization" "$build_dir/specialize-empty"
for mode in pipe state state-narrow state-wide ancestors grants local; do
  "$build_dir/empty-specialization-test" "$build_dir/$mode-specialization" \
    "$build_dir/specialize-empty" "--$mode"
done
