# Self-contained GameCodeBench environment: Stardew Valley + SMAPI + .NET build
# toolchain + agent harness, everything a trial needs baked in so the container can
# run with no network at all (same policy as the DarkRP suite).
#
# PREREQUISITE: game-files/ must exist in this build context, staged locally by
# scripts/prepare-task.sh from the operator's own Steam copy (app 413150, Linux
# depot 413153, see scripts/game-version.lock). Proprietary game files are never
# committed or redistributed; images built from this Dockerfile must stay private.
# .NET 10 SDK: the automate/2.6.x tree uses C# 14 features (field-backed
# properties, unbound generic nameof); SDK 8's compiler tops out at C# 12.
FROM mcr.microsoft.com/dotnet/sdk:10.0

# xvfb + Mesa llvmpipe: the game is MonoGame/DesktopGL and hard-requires an OpenGL
# context; every production headless-Stardew project runs a real X server with
# software GL (SDL's dummy video driver provides no GL and does not work).
# build-essential and git are baked in for the agent harness, same as DarkRP.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip xz-utils \
      xvfb xauth libgl1 libgl1-mesa-dri libopenal1 libfontconfig1 \
      python3 patch rsync git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pre-install the agent harness at BUILD time so the trial needs no network.
# Install into /usr/local/bin, NOT $HOME/.local/bin (the agent may run as a
# different user; a HOME-relative install fails with exit 127).
RUN UV_INSTALL_DIR=/usr/local/bin curl -LsSf https://astral.sh/uv/0.7.13/install.sh | \
      env UV_INSTALL_DIR=/usr/local/bin sh \
 && UV_TOOL_BIN_DIR=/usr/local/bin /usr/local/bin/uv tool install \
      mini-swe-agent --with 'litellm[proxy]' \
 && /usr/local/bin/uv --version \
 && command -v mini-swe-agent

ENV GAME_PATH=/opt/stardew \
    SMAPI_NO_TERMINAL=true \
    SMAPI_USE_CURRENT_SHELL=true \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    NUGET_PACKAGES=/opt/nuget

# --- Game + SMAPI -----------------------------------------------------------------
# game-files/ is the pinned Linux depot staged by scripts/prepare-task.sh.
COPY game-files /opt/stardew

# SMAPI 4.1.10 is the release synced with Stardew Valley 1.6.15 (the pinned game
# build). The installer patches the game's StardewValley launcher script, so
# /opt/stardew/StardewValley starts the modded game. Update checks are disabled:
# trials run with no network and must not depend on smapi.io.
ARG SMAPI_VERSION=4.1.10
RUN curl -fL -o /tmp/smapi.zip "https://github.com/Pathoschild/SMAPI/releases/download/${SMAPI_VERSION}/SMAPI-${SMAPI_VERSION}-installer.zip" \
 && unzip -q /tmp/smapi.zip -d /tmp/smapi \
 && printf '2\n\n' | "/tmp/smapi/SMAPI ${SMAPI_VERSION} installer/internal/linux/SMAPI.Installer" --install --game-path /opt/stardew \
 && rm -rf /tmp/smapi /tmp/smapi.zip \
 && test -x "/opt/stardew/StardewValley" \
 && printf '{\n  "CheckForUpdates": false\n}\n' > /opt/stardew/smapi-internal/config.user.json

# --- Mod source tree (what the agent works on) --------------------------------------
COPY StardewMods /app/StardewMods

# Warm the NuGet cache and prove the base tree compiles while the network is still
# available; trial-time builds run offline against /opt/nuget. Deploy is disabled
# here -- the verifier builds and deploys the agent's tree itself.
RUN dotnet restore /app/StardewMods/Automate/Automate.csproj \
 && dotnet build /app/StardewMods/Automate/Automate.csproj -c Release --no-restore \
      -p:GamePath=/opt/stardew -p:EnableModDeploy=false -p:EnableModZip=false

# --- Third-party mod, shipped as a compiled assembly only ---------------------------
# Its source is present in the build context but NEVER in the final image: the agent
# sees the DLL exactly as a player would, which is the point of this task.
COPY conflict-mod /tmp/conflict-mod
RUN dotnet build /tmp/conflict-mod/SmartMachines.csproj -c Release -p:GamePath=/opt/stardew \
 && mkdir -p /opt/stardew/Mods/SmartMachines \
 && cp /tmp/conflict-mod/bin/Release/SmartMachines.dll /tmp/conflict-mod/manifest.json \
       /opt/stardew/Mods/SmartMachines/ \
 && rm -rf /tmp/conflict-mod \
 && ls -la /opt/stardew/Mods/SmartMachines

# --- Verifier harness ----------------------------------------------------------------
# The harness source ships in the image; tests/test.sh compiles the task's private
# suite into it at verify time and deploys it as a SMAPI mod.
COPY gcb-harness /opt/gcb/harness/GcbHarness
RUN dotnet restore /opt/gcb/harness/GcbHarness/GcbHarness.csproj \
 && dotnet build /opt/gcb/harness/GcbHarness/GcbHarness.csproj -c Release --no-restore \
      -p:GamePath=/opt/stardew

# --- Deterministic fixture save -------------------------------------------------------
# Boot the game once under xvfb with the harness in gen-save mode: it creates a
# fixed-seed farm, runs the first night so the game writes the save, and exits.
# The resulting save folder name is recorded for the verifier.
RUN mkdir -p /opt/stardew/Mods/GcbHarness /logs/verifier \
 && cp /opt/gcb/harness/GcbHarness/bin/Release/GcbHarness.dll \
      /opt/gcb/harness/GcbHarness/manifest.json /opt/stardew/Mods/GcbHarness/ \
 && GCB_MODE=gen-save timeout 900 xvfb-run -a -s '-screen 0 1280x720x24 +extension GLX' \
      /opt/stardew/StardewValley || true \
 && ls "$HOME/.config/StardewValley/Saves" \
 && [ "$(ls "$HOME/.config/StardewValley/Saves" | wc -l)" -ge 1 ] \
 && ls "$HOME/.config/StardewValley/Saves" | head -1 > /opt/gcb/save-name.txt \
 && cat /opt/gcb/save-name.txt \
 && rm -rf /opt/stardew/Mods/GcbHarness

WORKDIR /app
