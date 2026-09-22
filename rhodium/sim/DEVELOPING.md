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
Run `nested-queue-test.rhm`, `nested-occurrence-test.rhm`, and their runtime
replay when changing this path. Two enclosing compositions wire individual
leaves in reverse declaration order to exercise packed assembly independently
of source order. Record payloads retain legal cross-field feedback through
those boundaries. The Verilator runner recursively checks the generated
`nested/` fixtures; repeated-instance replay uses independent traffic for
direct, mixed, and expanded choices.

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

## Captured map replay

`tests/mapped-queue-fixture.rhdl` retains maps on both sides of Queue. Each map
captures the same independently advancing register. `MapExpansion` supplies
handshake wiring plus generic core computation; Queue still selects its native
model before its portable body executes. No mapper-specific runtime callback or
extra state scheduler is introduced.

The mapped fixture preserves the existing scalar oracle's mathematical behavior,
so it reuses the same 512-cycle pre/post-edge stimuli, resets, stalls, wraparound,
and invalid payload comparisons. `mapped-queue-test.rhm` emits direct, expanded,
and default-optimized models under `RDS_MAP_DIR`. The host entry point creates
that directory as `mapped/`, and the Verilator runner descends into it. The
`--scalar-optimized` replay option includes optimized models in both interpreter
and generated-C modes. Keep generated artifacts outside the worktree.

`mapped-aggregate-fixture.rhdl` builds a record in the retained payload region.
One field reads the source argument; the other captures a different Queue output
field. This feedback is legal even with empty bypass. Preserve capture-leaf
precision through region extraction, composition wiring, and Queue query
projection. The mapped group emits scalar and aggregate models, including
optimized variants, and reuses both independent oracles for native and Verilator
replay. Run `mapped-aggregate-test.rhm` alongside `mapped-queue-test.rhm` when
changing this path.

The record fixture also selects same-field feedback for a negative case: empty
bypass must report a combinational cycle instead of accepting unsound dependencies.

`mapped-vector-fixture.rhdl` expresses the same feedback computation using two
vector elements. The shared host matrix emits its models under `RDS_VECTOR_DIR`;
the native and Verilator runners replay that directory against the aggregate
oracle. This checks vector packing independently of record field packing. Both
fixtures reject same-element/field feedback when empty bypass creates a cycle.
The replay's `--aggregate-only` switch permits this group without scalar models.

`mapped-wide-fixture.rhdl` uses two 65-bit vector elements, putting the second
at an unaligned packed offset and spanning three runtime words. Its external
ports expose every payload bit as a 64-bit low word and a one-bit high word.
`RDS_WIDE_DIR` holds these models; the runner's `wide-payload` marker selects the
matching Verilator bench and `--wide` oracle mode. Directed values exercise
64-bit carry and 65-bit wraparound alongside random upper bits, reset and stalls.

`mapped-nested-fixture.rhdl` wraps the same multiword values in a record containing
a vector of records. Its capture crosses all three aggregate boundaries while
preserving the field dependency. `RDS_NESTED_MAP_DIR` emits this group, which uses
the wide oracle and bench unchanged so every payload bit remains observable.

## Mixed retained pipe execution

`tests/mixed-pipe-fixture.rhdl` connects a depth-three bypass/replacement Queue
to each pipe family at one, two, and four stages. Valid-only variants include
flushable and nonflushable forms. `mixed-pipe-test.rhm` emits direct-Queue,
expanded-Queue, and optimized models under `RDS_PIPE_DIR`; pipe bodies always
use their portable provider and generic native lowering. The direct path has no
Queue expansion provider, proving selection occurs before its body is needed.

`mixed-pipe-runtime.py` owns the independent simultaneous-edge oracle, including
invalid payload retention, always-capture behavior, pending reset, flushes,
stalls, drain, and repeated evaluation. `runtime_model.py` shares only checked
runtime ABI access with the Queue replay; oracle state and transitions stay
independent of compiler/runtime implementation. The Verilator runner's `pipes/`
group uses the same stimuli and observable outputs.

## Assertion failure and retry

`tests/selective-effects-fixture.rhdl` declares clocked state and a named guarded
assertion through the public construct protocol, then expands that construct
beside either a native or portable Queue. The host matrix checks assertion
preservation exactly once after extraction and optimization. The replay runs
eight Queue configurations in direct, expanded, and optimized modes, each in
interpreter and generated C. It rejects repeated edges with distinct proposed
inputs, restores accepted inputs, and compares with a clean execution that never
attempted those edges. Diagnostic cycle numbers, register phase, Queue outputs,
reset/guard suppression, and future drain behavior expose premature publication.
The shared runner emits models under `RDS_EFFECTS_DIR` and runs this replay.
This gate does not establish arbitrary external callback semantics.

## Retained external host effects

`tests/selective-host-fixture.rhdl` declares two occurrences of one host-effect
construct. Its native provider binds the explicit host ABI; the portable sentinel
must never execute. `selective-host-runtime.py` binds occurrence callbacks and
checks registered 64-bit results, argument order, reset handling, and exactly one
invocation per occurrence on accepted edges. Repeated evaluation, failed
assertions, and an unbound later sibling must invoke no callbacks. Test both
interpreter and generated C, with and without optimization. The host entry point
emits this group under `RDS_HOST_DIR`.

Hardware preflight completes before callbacks run. Callback authors own external
side effects: a callback error cannot undo effects already performed by that
callback or an earlier sibling. Do not describe hardware-state retry guarantees
as transactional rollback of arbitrary external systems.

Host ABI verification requires five bound input words, the declared reset in
slot zero, one clock/reset association, no flags, and registered output queries
within the callback result count. Reject missing slots and combinational host
query dependencies during extraction rather than at runtime model loading.
The host replay also rejects a callback after it writes a tentative output,
verifying that neither this output nor hardware state is published.

## Migrated runtime regression suite

`make sim-runtime-regression-test` invokes
`tests/run-runtime-regressions.sh`, which builds compiler model helpers once and runs
package-local tests migrated from the previous simulator PR. It accepts an
existing runtime build directory, or creates an external build and runtime when
called without arguments. After the build-directory argument, optional test names
select a focused subset; unknown names fail before compilation. The selective host entry point invokes it after the
retained-construct replays.

- `bulk-cycles-test.cpp` compares batched edges with ordinary/reference execution,
  covering failed phases, callbacks, reset, state-bank parity, and reattachment.
- `parallel-state-test.cpp` compares snapshot-prefix splitting and independent
  state owners across component/replicated schedules and eight-worker execution.
- `regions_test.cpp` compares static-demand and eager execution across narrow/wide
  state, guards, scratch reuse, and multiple generated-code layouts.
- `fifo-width-test.cpp` checks inductive narrowing, cyclic bit growth, wide
  selection views, invalid selectors, and serialized opcode validation.
- `fifo-derived-test.cpp` checks enqueue-time derived fields at depths one through
  three and preserves the original transition for incompatible pipeline storage.

- `bit-relations-test.cpp` exhausts decoder inputs and control bits for narrow
  and multiword Boolean simplification, including overlapping first-match rows.
- `selector-columns-test.cpp` checks regrouped sparse selector columns against
  independent software, including disabled rows and serialized model round trips.
- `ring-selection-test.cpp` compares reference and compiled wide FIFO head/view
  selection under wraparound, strict invalid selectors, parallelism, and reattachment.

- `matcher-prefix-test.cpp` preserves grant reuse only when update operands match
  the complete request prefix, and replays stalls and reset.
- `packed_matcher_test.cpp` checks arbitration against independent software,
  including prefix feedback, grant reuse, split priority ownership, and reattachment.
- `idle-fifo-test.cpp` compares inductively empty FIFO folding with original
  execution, retaining bypass previews, strict diagnostics, and failed-edge retry.
- `stationary-matcher-test.cpp` preserves independent query operands and priority
  state through folding, including invalid grants and failed host callbacks.
- `fifo-batch-test.cpp` checks batched control preparation against reference
  execution with wide payloads, late dependencies, and host-publication failures.

- `contract-kernel-test.cpp` checks captured maps, guarded branches, feedback,
  snapshot updates, and malformed kernel programs across generated-code modes.
- `decoder-specialization-test.cpp` checks constant-field specialization against
  independent first-match/default decoding, including state and reattachment.
- `payload-pool-test.cpp` checks concurrent ingress and shared selection without
  leaking stale previews or failed publication into committed payload storage.
- `payload-lifetime-test.cpp` checks ordered lifetime sharing and exact capacity,
  preserving intermediate readers and control independence from pooled payloads.
- `payload-exchange-test.cpp` checks routed payload ownership and handle layouts
  against original execution, including multiword data and unsafe-sharing rejection.
- `flow_cache_test.cpp` checks cross-object cache keys, independent publication,
  speculative retry, and compiled-library reattachment.
- `semantic_structure_test.cpp` checks demanded-field provenance, feedback,
  pruning, wide keys, and malformed semantic mappings.

- `flow-regions-test.cpp` checks contract-guided grouping against independent
  arithmetic while preserving shared observers and analysis-only ordering.
- `lifted-primitives-test.cpp` checks control-mask boundaries, packet ownership,
  scoreboard old-state semantics, and failed-host retry across generated schedules.

These preserve the original independent oracles. Remaining compiler optimization,
object-family, arithmetic, and frontend fixture migration is tracked in the
[selective lowering plan](../core/SELECTIVE_LOWERING_PLAN.md).

## Ordinary core IR regression suite

`make sim-core-regression-test` invokes `tests/run-core-regressions.sh`. It emits
ordinary core fixtures with a fresh compiled root, then runs the migrated
compiler interchange, typed semantic exchange, runtime-oracle, and generated-C
suites. The selective host runner invokes this independent core-only path after
its retained-construct and standalone runtime groups. An optional existing
artifact directory can be supplied to the script; elaboration still receives
a newly created compiled root. Generated outputs stay outside the checkout.

`emit-fixtures.rhm` owns arithmetic widths across machine-word boundaries,
aggregate feedback, hierarchy, memory, assertions, and pipeline fixtures. The
Python suites share only runtime ABI access; independent arithmetic and state
oracles remain in `runtime_test.py`. Preserve raw/reference variants, malformed
image diagnostics, repeated evaluation, failed publication, and generated-library
identity checks when adapting these fixtures. Runtime attachment fixtures in
`codegen_test.py` construct FIFO/broadcast object ABI models directly; library
recognition after elaboration is not part of this runtime test. The runner also
checks the x86 assembly path when the host toolchain supports it.

`inspect_ir.py` owns source-mapped comparisons of model stages, runtime plans,
generated commands, and optional static machine-code reports. Its migrated
`tests/inspection_test.py` uses the core fixture batch to check shared lookups,
sparse/default decoder selection, source provenance, and real compiler-output
disassembly. The core regression runner includes this inspection gate.

## Native object and replication regression suite

`make sim-object-regression-test` runs `tests/run-object-regressions.sh` with a
fresh compiled root. The selective host runner includes this gate. All simulator
runner artifact roots honor `TMPDIR`, allowing validation on a filesystem with
available quota without writing generated files into the checkout.
`emit-object-models.py` constructs explicit runtime object ABI fixtures; it does
not identify library bodies after expansion. `emit-object-rtl.rhm` independently
compiles the actual Flow implementations as generic RTL references. Preserve
these two fixture paths so native-versus-RTL comparisons remain independent.

`native_objects_test.py` retains the previous protocol oracles and descriptor
rejection checks in interpreter and generated-C modes. It covers FIFO payload
widths 8/65/4096 and depths 1/3/1024, payload-free control variants, offers,
round-robin/packet arbitration, valid-only pipes, and broadcasts. These explicit
payload-free ABI fixtures do not authorize dropping observable payloads from
a public construct contract.

`emit-replication.rhm` retains byte/work-budget checks and ordinary shared-cone
fixtures. Its package-local `shared-query-fixture.rhdl` elaborates retained Queue
and selects `QueueNative`; replication must preserve one Queue update owner
while splitting independent query consumers. Runtime replay checks bounded
replication, automatic scheduling, reset, and shared-state recurrence.

The same runner emits the canonical standard-library examples with
`emit-library.rhm` and replays `library_test.py`. These examples exercise generic
core-IR fallback, including scoreboard diagnostics, queue options, pipe latency,
arbitration, and credited transport. They do not claim direct target registrations
for every library construct. Raw, optimized, parallel, generated-C, and supported
x86 assembly execution retain the original independent protocol oracles.
