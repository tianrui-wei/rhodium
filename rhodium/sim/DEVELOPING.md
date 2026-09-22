<!-- Owns extraction, runtime architecture, state ownership, and simulator validation. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developing native simulation

Read the [public contract](README.md) and the repository
[dependency inventory](../DEVELOPING.md). This package consumes core IR;
frontend, standard-library and SoC recognition belongs in explicit downstream
adapters under `sims/native/`.

## Implementation boundaries

| Component | Responsibility |
|---|---|
| `extract.rhm`, `objects.rhm` | Occurrence expansion, typed extraction and explicit model/contract bindings |
| `model.rhm`, `inspect.rhm` | Binary/JSON serialization and source inspection |
| `optimize.rhm`, `replicate.rhm` | Compatibility adapters to the standalone compiler |
| `compiler/` | Graph validation, transformations, reports and binary emission |
| `runtime/model.c`, `internal.h` | Validated loading, model storage and lifecycle |
| `runtime/schedule.c`, `partition.c`, `regions.c` | Fixed scheduling, ownership, temporary allocation and bounded region construction |
| `runtime/execute.c`, `objects.c` | Reference execution and semantic state transitions |
| `runtime/codegen*.c` | Ahead-of-time operations, kernels, storage and publication |
| `runtime/offers.c` | Eligible persistent-worker bulk execution |
| `runtime/inspect.c` | Plans and source/storage provenance |

Keep the execution image independent of JSON and frontend packages. The reference
interpreter and generated code consume the same validated semantics. Host compiler
invocation belongs in tools, not in the emitter. Binary versions, object kinds,
operation numbers and generated-library fingerprints must remain coordinated
between serializers, loader, optimizer and emitter.

## Publication and ownership

Evaluation reads committed state. Preparing an edge may compute private proposals
but must not mutate observable hardware state. Check assertions, partial operations
and host effects before publishing registers, objects, host outputs or SRAM writes.
A failed edge must support retry and compiled-library replacement without leaking
speculative updates. Derived caches may change only when their contents remain
valid for exact input keys.

Flip-flop reads refer to the current bank throughout evaluation. A successful
edge publishes the next bank by swapping its role. SRAM retains its allocation;
only accepted write addresses/data/enables are staged and applied at publication.
Parallel state preparation writes disjoint owner storage. A barrier or corresponding
release/acquire dependency must cover every cross-owner read before reuse.

Persistent workers can execute multiple edges with unchanged public inputs.
The offer backend requires its eligibility proof; host callbacks, object tracing,
incompatible state modes and unsupported epilogues use ordinary edge execution.
Zero/odd/even batches, reset, delayed workers and failed edges must retain the
same observable boundaries. Do not infer lookahead from an API batch size.

## Transformations and generated storage

Pure-region fusion may forward local words into C expressions and defer mux arms
only when dependencies, totality and diagnostics permit it. Shared consumers,
state, SRAM and host effects remain explicit boundaries. Source conditional
labels suggest candidates but do not prove safe ordering.

Queries read current object state. Fused preparation must preserve old-state
previews and publish each owner exactly once. In particular, reset can clear
queue occupancy while retaining the source queue's accepted payload write.
Do not assume invalid payloads are unobservable without a proven use boundary.

Cache keys must include every changing dependency and all significant bits.
Reattachment invalidates derived caches or proves their exact keys remain valid.
Compact scratch uses declared widths, checked storage provenance and lifetime
interference; byte packing must not introduce overlapping concurrent writes.
Inline vector/assembly kernels require portable fallbacks and the same fixed-width
semantics, including overshifts and invalid selections.

Payload transformations belong in the [compiler](compiler/DEVELOPING.md).
Pooling preserves exact capacity, ownership, reset and retained field access.
An index is not a host pointer, and a stable pool address alone does not authorize
reuse while an old snapshot still references a slot.

## Validation

The [test runner](tests/run-selective.sh) exercises retained selection and
native/expanded Queue replay. This dependent worktree restores the previous
compiler/runtime; its broader optimization suite still needs migration.
Use independent arithmetic/queue oracles and original-versus-compiled replay,
including malformed supported inputs, repeated evaluation, failed publication,
reattachment, strict/release behavior and parallel execution. Changes spanning
extraction, image layout and execution require the complete owning suite.

Racket fixture commands use a new `PLTCOMPILEDROOTS` directory and `racket -y`;
reuse that directory within the validation batch. Offline C/C++ tests can reuse
retained fixtures without elaboration. Sanitizer flags for the runtime and
standalone compiler are separate. Keep generated code, profiles and raw timing
results outside version control.

Inspect per-worker work, wait time, storage and generated instructions before
attributing a speed change. Compare identical target inputs and host optimization
flags; verify behavior separately from timing. A smaller graph or a faster isolated
kernel does not establish a whole-SoC improvement.

## Retained occurrence extraction

`extract.rhm` calls the public core resolver before building execution objects.
Generic module occurrences keep their core operations; selected native leaves
carry contract ports and no portable body. Both contribute to the same model,
scheduler, prepare phase, and simultaneous publication. Boundary connections use
port names so portable implementation port order cannot change the ABI.
`objects.rhm` owns `NativeImplementation`; library registration remains in
`sims/native`. `native-contract.rhm` checks packed input/output ranges, complete
nonoverlapping output coverage, leaf-sensitive dependency containment, declared
effects, and the supported Queue clock/reset/query ABI. Native semantics still
require owner-provided implementations and differential validation.
`composition.rhm` maps verified scoped connections to packed port ranges.
Composition occurrences allocate their children before resolving connections;
input and output projections follow those connections lazily, preserving
field-level dependencies across nested boundaries. Native leaves and portable
core children retain separate occurrence state under the shared schedule.
Run `nested-queue-test.rhm` and its interpreter/generated-C replay when changing
this path; its two enclosing compositions wire individual leaves in reverse
declaration order to exercise packed assembly independently of source order.

The focused host tests prove skipped expansion and occurrence-local choices.
Runtime replay checks every public output before/after edges against a separate
oracle, including defined invalid payloads and reset-time storage writes. It
runs direct and expanded implementations in interpreter and generated-C modes;
the Verilator runner adds the portable SystemVerilog path. Repeated Queue
instances compare direct, mixed, and expanded choices with independent traffic.
`ci-host-native-test` owns this host coverage; package/import changes also run
boundary and CI-routing audits.

Queue payload queries use `NativeSlice` only for a matching payload projection.
The extractor pads unobserved input bits to preserve the runtime query width,
then observes only the certified output slice. State capture still reads the
complete payload. Keep cache keys distinct for different dependency slices and
assemble native outputs by packed offset, independent of descriptor order.
The aggregate fixture deliberately connects one output field to a different
input field; it detects false whole-payload cycles and swapped packed ranges.
Run the contract rejection tests, aggregate replay, and the default optimizer
path when changing this representation. CI installs the standalone compiler's
JSON and Boost headers for the native host lane.
