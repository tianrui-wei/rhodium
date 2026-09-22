<!-- Owns library-specific native target registrations and their validation. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developing native adapters

Adapters import public construct identities from their owning libraries and
native target records from `rhodium/sim`. They must not probe a portable
implementation or recognize display names. Core and frontend never import these
adapters. Queue's native lowering preserves pipe/flow dependencies and the
existing runtime's simultaneous state publication.

Use the mixed Queue fixture under `rhodium/sim/tests` to check skipped expansion,
ordinary RTL around the selected construct, and direct/expanded cycle behavior.
Keep queue-specific registration here rather than in the generic extractor.

## Harness and benchmark regression helpers

`mini-loader.h` and `workload-host.h` own deterministic smoke-loader traffic,
trace hashing, and sized host-transaction adaptation. `benchmark-single.cpp`
owns single-worker timing validation, subprocess isolation, immutable artifact
audits, and optional matched profile-guided builds. These are harness utilities;
they do not supply construct recognition or a complete executable SoC harness.
`mini-smoke.c` is the runtime driver used by those matched builds and consumes
an externally emitted compatible SoC model. The helper regression does not
establish an end-to-end SoC boot or profile-guided performance result.

Run `bash sims/native/tests/run.sh` for the migrated benchmark-audit,
250,000-case loader-trace, and host-transaction regressions. An optional existing
artifact directory can be supplied; generated binaries and scratch files stay
outside the checkout and respect `TMPDIR`. The selective simulator runner
includes this gate. Keep original transaction and timing-validation oracles
when changing these helpers.

The same runner checks `profile-layout.py` sample decoding and allocation
attribution without requiring PMU access, and `scratch-inspect.cpp` spill-slot
eligibility, SIMD register aliases, and ELF load-sample attribution. Their
package-local regressions preserve conservative rejection of overlapping slots
and malformed records. Parser validation does not claim live PMU collection or
dynamic performance measurements on this host.
