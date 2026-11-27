# Self-contained GameCodeBench environment: Stardew Valley + SMAPI + .NET build
# toolchain + private verifier harness, everything a trial needs baked in so the container can
# run with no network at all (same policy as the DarkRP suite).
#
# PREREQUISITE: the Rhenium plugin generates this build context and stages
# game-files/ from the operator's pinned owned Linux copy (app 413150, depot
# 413153; see the pack-level private/harbor/scripts/game-version.lock). Proprietary game files are never
# committed or redistributed; images built from this Dockerfile must stay private.
FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim@sha256:e2f26f26169fd10d6f1b426e01c97397717b32e9d5ab4ee4a7d5497ed9403007

# xvfb + Mesa llvmpipe: the game is MonoGame/DesktopGL and hard-requires an OpenGL
# context; every production headless-Stardew project runs a real X server with
# software GL (SDL's dummy video driver provides no GL and does not work).
# build-essential and git support offline submission builds and patch application.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip xz-utils \
      xvfb xauth libgl1 libgl1-mesa-dri libopenal1 libfontconfig1 \
      python3 patch rsync git build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV GAME_PATH=/opt/stardew \
    SMAPI_NO_TERMINAL=true \
    SMAPI_USE_CURRENT_SHELL=true \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    NUGET_PACKAGES=/opt/nuget

# --- Game + SMAPI -----------------------------------------------------------------
# game-files/ is the pinned Linux depot staged into temporary Hub cache by the plugin.
COPY game-files /opt/stardew

# SMAPI 4.1.10 is the release synced with Stardew Valley 1.6.15 (the pinned game
# build). The installer patches the game's StardewValley launcher script, so
# /opt/stardew/StardewValley starts the modded game. Update checks are disabled:
# trials run with no network and must not depend on smapi.io.
ARG SMAPI_VERSION=4.1.10
ARG SMAPI_SHA256=8c127148a76c890e485aea73910189dc41c80f822c2a0a5e3b0e762b4ee3a93e
RUN curl -fL -o /tmp/smapi.zip "https://github.com/Pathoschild/SMAPI/releases/download/${SMAPI_VERSION}/SMAPI-${SMAPI_VERSION}-installer.zip" \
 && echo "${SMAPI_SHA256}  /tmp/smapi.zip" | sha256sum -c - \
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
# .NET 6 returns an empty ApplicationData path when $HOME/.config is absent, so SMAPI
# would resolve its log directory against the game's launcher and exit before saving.
RUN mkdir -p /opt/stardew/Mods/GcbHarness /logs/verifier "$HOME/.config" \
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
