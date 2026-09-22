<!-- Describes construct-identity adapters for native simulation. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Native simulation adapters

`queue.rhm` exports `QueueNative`, a target lowering registered against Flow's
public `QueueConstruct` identity. Pass it in `compile_simulation`'s `~lowerings`
list and pass `QueueExpansion` in `~expansions` for portable fallback. Selection
happens before the Queue implementation executes.

The adapter supports mixed native/portable execution, including nested
compositions and captured aggregate payload computations. See the
[simulator contract](../../rhodium/sim/README.md) for supported timing, state,
and effect behavior, and the [selective lowering plan](../../rhodium/core/SELECTIVE_LOWERING_PLAN.md)
for validation evidence and performance gates.
