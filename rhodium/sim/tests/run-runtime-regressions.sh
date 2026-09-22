#!/usr/bin/env bash
# Builds migrated state-publication and scheduling regressions without frontend elaboration.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
regression_dir="${1:-$(mktemp -d /tmp/rhodium-runtime-regressions.XXXXXX)}"
regression_dir="$(realpath "$regression_dir")"
cd "$repo_dir"
if [[ ! -f "$regression_dir/librhodium_sim.so" ]]; then
  "${CC:-cc}" -std=c17 -pthread -O2 -g -Wall -Wextra -Werror -fPIC -shared \
    ${RDS_SANITIZER_FLAGS:-} rhodium/sim/runtime/*.c -ldl -o "$regression_dir/librhodium_sim.so"
fi
for unit in model semantic snapshot; do
  "${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror \
    -c "rhodium/sim/compiler/$unit.cpp" -o "$regression_dir/regression-$unit.o"
done
for source in bulk-cycles-test parallel-state-test regions_test; do
  "${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror \
    "rhodium/sim/tests/$source.cpp" "$regression_dir"/regression-{model,semantic,snapshot}.o \
    -L"$regression_dir" -lrhodium_sim -ldl -Wl,-rpath,"$regression_dir" -o "$regression_dir/$source"
  regression_timeout=120
  # The demand matrix compiles 74 generated libraries before its 1,000-cycle replay.
  if [[ "$source" == regions_test ]]; then regression_timeout=600; fi
  timeout "$regression_timeout" "$regression_dir/$source" "$regression_dir/$source-models"
done
printf 'Runtime regression artifacts: %s\n' "$regression_dir"
