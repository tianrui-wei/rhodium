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
