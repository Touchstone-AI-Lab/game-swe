#!/usr/bin/env bash
set -euo pipefail

root="/workspace/fargos-mutant"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Common/Systems/Recipes/MiscRecipeSystem.cs" "$root/Common/Systems/Recipes/MiscRecipeSystem.cs"
cp "$oracle/Content/Items/Tiles/EnchantedTreeSheet.cs" "$root/Content/Items/Tiles/EnchantedTreeSheet.cs"
cp "$oracle/Content/Items/Tiles/EnchantedTreeTileEntity.cs" "$root/Content/Items/Tiles/EnchantedTreeTileEntity.cs"
