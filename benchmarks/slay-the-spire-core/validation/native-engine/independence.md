# Task independence and shared-source boundaries

The seven additions exercise distinct repair contracts and have separate frozen
source, public reports, private suites and references. No existing task is split
or renamed to increase the count.

| Task | Reference repair targets | Behavioral contract |
|---|---|---|
| Original load order | GraphTS, ClassPatchInfo, ParameterPatchInfo | Dependency ordering and generated parameter handling |
| Original mod identity | Loader, ModInfo | Descriptor identity, version parsing and dependency matching |
| Original loader internals | ModInfo, SpireReturn, ParameterPatchInfo, PostfixPatchInfo | Cached descriptors and generated patch control/result behavior |
| New descriptions | BaseMod DynamicTextBlocks | Nested expansion, numeric matching, coherent values and actual display refresh |
| New block | StSLib BlockModifierManager, BindingPatches, BlockModifierPatches | Accepted capacity, targeted losses and nested callback accounting |
| New enum | ModTheSpire Patcher, EnumBusterReflect | Alias identity, fresh standard queries and mod switch dispatch after mutation |
| New icons | StSLib TipBoxCustomIcons | Smart width, constrained layout and Chinese description height with custom icons |
| New Stasis | Downfall StasisOrb, StasisEvokeIfRoomInHandAction, PlaceActualCardIntoStasis, PlaceRandomCardIntoStasisAction, PlaceRandom1CostIntoStasis | Exactly-once physical transfer, repeated callbacks, protected slots and fresh card ownership on rechannel |
| New event transitions | BaseMod PhasedEvent, CombatPhase | Finite lifecycle redirects, stale reopen decisions and clearing combat continuations |
| New campfire selection | Downfall Guardian cancellation patch and socket effect | Back navigation, gem consumption and ownership of subsequent native Smith selections |

The new reference target sets are pairwise disjoint and have no file overlap with
the original three reference targets. This is source/contract separation, not a
claim of statistically independent outcomes. BaseMod/StSLib depend on the
same loader and game, and all ModTheSpire tasks expose overlapping baseline source.
Hold out by upstream source family when building training/evaluation splits.

The old validation notes also describe an excluded enum-injection
candidate. It is not one of the original pack's shipped three tasks. Its presence in the
authoring history must not be confused with an additional shipped task or hidden
to imply that enum work had never been tried before.

The campfire-selection task uses original Downfall source and actual native OS mouse/keyboard input. Its Back navigation and abandoned selection ownership are distinct from existing Stasis capture/evoke behavior, BaseMod phase transitions and the retired Packmaster campfire-button refresh. The r1 formal controls were rejected because software rendering dropped inputs under a CPU quota. r2 pinned renderer threads and reproduced the unchanged cases and both complete repairs under that quota. No prompt, expectation or repair was hardened in response to a model result. The compilation, expiration, modal, ghost-wheel, hit-resolution, card-transit, stun, power-dispatch, expression-types, Gremlin-event, VFX-clock and extra-effect-lifetime candidates remain retired. Earlier transfer/persistence and reconstruction candidates remain excluded.
