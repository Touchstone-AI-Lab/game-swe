#!/usr/bin/env bash
set -euo pipefail

root="/workspace/terraria-overhaul"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Core/Data/DataStorage.cs" "$root/Core/Data/DataStorage.cs"
cp "$oracle/Core/Data/SparseSet.cs" "$root/Core/Data/SparseSet.cs"
cp "$oracle/Core/Data/Entities.cs" "$root/Core/Data/Entities.cs"
cp "$oracle/Core/Chunks/Chunks.cs" "$root/Core/Chunks/Chunks.cs"
cp "$oracle/Utilities/BitMasks.cs" "$root/Utilities/BitMasks.cs"
