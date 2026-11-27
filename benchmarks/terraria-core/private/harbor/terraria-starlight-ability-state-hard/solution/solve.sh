#!/usr/bin/env bash
set -euo pipefail

root="/workspace/starlight-river"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Content/Abilities/Ability.cs" "$root/Content/Abilities/Ability.cs"
cp "$oracle/Content/Abilities/AbilityHandler.cs" "$root/Content/Abilities/AbilityHandler.cs"
cp "$oracle/Content/Abilities/ShardSet.cs" "$root/Content/Abilities/ShardSet.cs"
cp "$oracle/Content/Abilities/InfusionItem.cs" "$root/Content/Abilities/InfusionItem.cs"
cp "$oracle/Content/Abilities/InfusionTier.cs" "$root/Content/Abilities/InfusionTier.cs"
cp "$oracle/Content/Packets/AbilityProgress.cs" "$root/Content/Packets/AbilityProgress.cs"
cp "$oracle/Content/Packets/StartAbility.cs" "$root/Content/Packets/StartAbility.cs"
