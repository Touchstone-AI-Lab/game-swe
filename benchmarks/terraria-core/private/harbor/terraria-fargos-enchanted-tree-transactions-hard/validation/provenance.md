# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/Fargowilta/Fargowiltas`
- Commit: `85246bb5e4d3b225028b1bf73cd6d99b81674307`
- Mod version: 3.4
- License: MIT, Copyright (c) 2024 Fargo Team
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The retained upstream files and their Git blob IDs are recorded in
`upstream-git-blobs.txt`. The starter modifies only the three documented
production files. License, build metadata, and README are retained for source
context; no asset, binary, build output, cache, or Git metadata is packaged.

## Real production path

`EnchantedTreeSheet.RightClick` performs the interaction transaction.
`EnchantedTreeTileEntity` owns persistence, binary synchronization, policy,
and global updates. `MiscRecipeSystem.PostSetupRecipes` consumes the completed
tModLoader recipe table to build branches. Private tests compile and invoke
those exact files; the engine doubles only supply Terraria/tModLoader-owned
types.

## Historical grounding

Upstream commits `97f0e061e46f5f5277f0ece3ba2118e4f107d77a` and
`85246bb5e4d3b225028b1bf73cd6d99b81674307` repaired related Enchanted Tree
interaction, prefix, eligibility, lifecycle, and cooldown failures. The task
extends that same invariant set with ordinary collection and snapshot
replacement failures visible in the frozen implementation.

Revision 2 additionally preserves the branch graph and paid-duplication state
machine already present in the frozen file. Commit
`f45bd3f8601391d6785e6d05b549d5d9221ab9b1` introduced the two-times-value
`BuyItem` transaction, and `97f0e061e46f5f5277f0ece3ba2118e4f107d77a`
fixed stored-prefix propagation for the resulting item. The new checks cover
parent/layer linkage, non-duplicating expansion, descendant collapse, cursor
ownership, payment atomicity, item metadata, and the existing sync calls.

Revision 4 stays on those production paths. It treats repeated
`PostSetupRecipes` calls as replacement snapshots, formalizes the existing
`previousItem`/`layer` fields as an ordered forest on the unchanged packet
format, repairs that index graph when runtime deletion compacts the list,
uses ancestry rather than global depth for branch collapse, and prevents a
duplicate registry coordinate from updating one tile entity twice per frame.

## Fairness and uniqueness

All 78 assertions map to a prompt sentence in `case-contracts.tsv`. No private
case relies on visual output or an undisclosed item identity. This task differs
from task 01: it evaluates a UI/tile transaction, a tModLoader lifecycle hook,
and mutable tile-entity collections rather than a binary compression format.
The repeated Python verifier shell is documented shared Terraria harness
infrastructure; the production sources, prompt, oracle, and C# contract suite
are independently authored.

## Revision history

Revision 3 added nine public-contract cases for malformed binary snapshots and
transactional receive.

Revision 4 adds 28 explicit cases across graph validation, graph compaction,
replacement recipe setup, ancestry-specific collapse, and duplicate registry
entries. Local controls are oracle 78/78 and starter 30/78.
