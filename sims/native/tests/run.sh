#!/usr/bin/env bash
# Validates native harness transactions, trace hashing, and benchmark audit helpers.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
test_dir="${1:-$(mktemp -d "${TMPDIR:-/tmp}/rhodium-native-harness.XXXXXX")}"
test_dir="$(realpath "$test_dir")"
cd "$repo_dir"
for test in benchmark_single_test loader-trace-test workload-host-test; do
  "${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror \
    "sims/native/tests/$test.cpp" -o "$test_dir/$test"
  "$test_dir/$test"
done
printf 'Native harness regression artifacts: %s\n' "$test_dir"
