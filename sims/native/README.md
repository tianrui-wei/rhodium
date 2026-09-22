<!-- Describes construct-identity adapters for native simulation. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Native simulation adapters

`queue.rhm` exports `QueueNative`, a target lowering registered against Flow's
public `QueueConstruct` identity. Pass it in `compile_simulation`'s `~lowerings`
list and pass `QueueExpansion` in `~expansions` for portable fallback. Selection
happens before the Queue implementation executes.

This adapter is being integrated with the native runtime. The full completion
criteria remain in the [selective lowering plan](../../rhodium/core/SELECTIVE_LOWERING_PLAN.md).
