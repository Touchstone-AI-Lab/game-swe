# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/ProjectStarlight/StarlightRiver`
- Commit: `d367416dcadfe68a541a5821a0c4be86b42db219`
- Mod version: Starlight River 0.2.9.4
- License: GPL-3.0
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The starter retains frozen upstream production code and metadata with LF
normalization plus two documented syntax-only rewrites required by the pinned
.NET 8 compiler: an auto-property `field` expression becomes an explicit
backing field, and a null-conditional assignment becomes an equivalent null
check. The compatibility patch and original Git blob IDs are retained. The
package includes source and license only; assets, referenced DLLs, Git data,
caches, and build output are excluded.

## Real production path

`AbilityHandler` owns the real ModPlayer persistence, infusion array, stamina,
tick transition, and runtime ability instances. `Ability` initiates local
transitions and start packets. `AbilityProgress` synchronizes join progression,
while `StartAbility` resolves and applies remote active types. `ShardSet` and
`InfusionItem` are their actual retained state types. The evaluator invokes
these production files; doubles supply engine/NetEasy boundaries only.

## Historical grounding

The upstream history contains `77bf60a7ab82f26e9585ba11f885305495775da2`
("ABILITIES SYNC"), `92e0f3dfd2513fc77ca644d61e8431b6e55965ef`
("misc. sync improvements and fixes"),
`ac6e18fcc1c581b929027590cab38385bca2b5b9`
("fix for fresh characters having unlocked abilities"), and
`e8957da9f931da0f7c63b01acda851bc46793d1e`
("Infusion right click fix"). At the frozen revision, saving filters away empty
infusion slots, loading mutates live state inside one broad catch, cloning is
shallow, transition hooks run before the queued state commits, and both
packets trust declared identity and unchecked types.

## Fairness and uniqueness

All 84 cases map to explicit prompt clauses. The prompt states tag keys,
legacy compatibility, counts, mask bits, clone ownership, tick timing,
transaction boundaries, hook-failure outcomes, reentrant transition timing,
callback snapshots, and sender/relay behavior. Tests use visible fake
abilities and item factories with deterministic delivery metadata; no UI,
rendering, random world, or hidden type names are involved. This task is
distinct from previous tasks because it repairs one player progression state
across object ownership, delayed gameplay hooks, persistence, and two
authoritative replication messages. The revised ownership group checks the
same exact-instance invariant after lock, successful load, infusion change,
and accepted progress replacement; hooks are asserted only after `PreUpdate`,
as stated in the public contract.

## Revision history

The 69-case death-transition revision passed 69/69 oracle and 13/69 starter
controls.

Revision 3 is a substantial same-path state-machine redesign. Ability
lifecycle, fixed update, active update, visual, and draw hooks are mod-defined
callbacks that can synchronously mutate the same handler or throw. The new
contract makes activation rollback, retirement, reentrant next-tick requests,
death suppression, fixed ownership snapshots, same-tick active reconciliation,
and visual fault isolation deterministic. The prompt states each observable
phase and failure outcome. The oracle passes 84/84 and the frozen starter
14/84.
