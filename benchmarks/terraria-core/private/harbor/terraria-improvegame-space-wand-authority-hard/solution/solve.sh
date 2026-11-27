#!/usr/bin/env bash
set -euo pipefail

root="/workspace/improvegame"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Content/Items/SpaceWand.Shapes.cs" "$root/Content/Items/SpaceWand.Shapes.cs"
cp "$oracle/Content/Items/SpaceWand.Operations.cs" "$root/Content/Items/SpaceWand.Operations.cs"
cp "$oracle/Content/Packets/SpaceWandOperation.cs" "$root/Content/Packets/SpaceWandOperation.cs"
