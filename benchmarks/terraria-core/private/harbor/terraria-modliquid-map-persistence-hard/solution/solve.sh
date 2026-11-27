#!/usr/bin/env bash
set -euo pipefail

root="/workspace/mod-liquid-lib"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/IO/MapLiquidIO.cs" "$root/IO/MapLiquidIO.cs"
cp "$oracle/Hooks/MapHelperHooks.cs" "$root/Hooks/MapHelperHooks.cs"
cp "$oracle/Hooks/MapLoaderHooks.cs" "$root/Hooks/MapLoaderHooks.cs"
cp "$oracle/Hooks/WorldMapHooks.cs" "$root/Hooks/WorldMapHooks.cs"
cp "$oracle/ModLoader/MapEntry.cs" "$root/ModLoader/MapEntry.cs"
cp "$oracle/ModLoader/MapLiquidLoader.cs" "$root/ModLoader/MapLiquidLoader.cs"
