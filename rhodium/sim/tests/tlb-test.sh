#!/usr/bin/env bash
# Builds and runs Sv39 native-versus-RTL and failed-publication oracle replay.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
fixture_dir="$(realpath "${1:?supply an emitted TLB fixture directory}")"
cd "$repo_dir"
"${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror rhodium/sim/tests/tlb_test.cpp \
  -L"$fixture_dir" -lrhodium_sim -Wl,-rpath,"$fixture_dir" -o "$fixture_dir/tlb-test"
"$fixture_dir/tlb-test" "$fixture_dir"
