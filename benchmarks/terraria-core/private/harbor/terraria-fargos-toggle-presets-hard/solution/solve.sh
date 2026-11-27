#!/usr/bin/env bash
set -euo pipefail

root="/workspace/fargos-souls"
oracle="$(cd "$(dirname "$0")" && pwd)/after"

cp "$oracle/Core/Toggler/Toggle.cs" "$root/Core/Toggler/Toggle.cs"
cp "$oracle/Core/Toggler/ToggleLoader.cs" "$root/Core/Toggler/ToggleLoader.cs"
cp "$oracle/Core/Toggler/ToggleBackend.cs" "$root/Core/Toggler/ToggleBackend.cs"
cp "$oracle/Core/Toggler/SoulCheck.cs" "$root/Core/Toggler/SoulCheck.cs"
