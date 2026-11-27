# Trusted clean-room synthetic Stardew build template. Proprietary game files are
# staged only by the existing managed runtime builder and remain local.
FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim@sha256:e2f26f26169fd10d6f1b426e01c97397717b32e9d5ab4ee4a7d5497ed9403007

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

COPY game-files /opt/stardew

ARG SMAPI_VERSION=4.1.10
ARG SMAPI_SHA256=8c127148a76c890e485aea73910189dc41c80f822c2a0a5e3b0e762b4ee3a93e
RUN curl -fL -o /tmp/smapi.zip "https://github.com/Pathoschild/SMAPI/releases/download/${SMAPI_VERSION}/SMAPI-${SMAPI_VERSION}-installer.zip" \
 && echo "${SMAPI_SHA256}  /tmp/smapi.zip" | sha256sum -c - \
 && unzip -q /tmp/smapi.zip -d /tmp/smapi \
 && printf '2\n\n' | "/tmp/smapi/SMAPI ${SMAPI_VERSION} installer/internal/linux/SMAPI.Installer" --install --game-path /opt/stardew \
 && rm -rf /tmp/smapi /tmp/smapi.zip \
 && test -x "/opt/stardew/StardewValley" \
 && printf '{\n  "CheckForUpdates": false\n}\n' > /opt/stardew/smapi-internal/config.user.json

COPY mod /app/mod
RUN dotnet restore /app/mod/Synthetic.sln \
 && dotnet build /app/mod/Synthetic.sln -c Release --no-restore \
      -p:GamePath=/opt/stardew -p:EnableModDeploy=false -p:EnableModZip=false

COPY gcb-harness /opt/gcb/harness/GcbHarness
RUN dotnet restore /opt/gcb/harness/GcbHarness/GcbHarness.csproj \
 && dotnet build /opt/gcb/harness/GcbHarness/GcbHarness.csproj -c Release --no-restore \
      -p:GamePath=/opt/stardew

# .NET 6 returns an empty ApplicationData path when the XDG directory is absent.
# Create it before SMAPI starts, otherwise its relative StardewValley/ErrorLogs
# path collides with the game's StardewValley launcher.
ENV XDG_CONFIG_HOME=/opt/gcb/user-config
RUN mkdir -p /opt/stardew/Mods/GcbHarness /logs/verifier "$XDG_CONFIG_HOME" \
 && cp /opt/gcb/harness/GcbHarness/bin/Release/GcbHarness.dll \
      /opt/gcb/harness/GcbHarness/manifest.json /opt/stardew/Mods/GcbHarness/ \
 && GCB_MODE=gen-save timeout 1800 xvfb-run -a -s '-screen 0 1280x720x24 +extension GLX' \
      /opt/stardew/StardewValley || true \
 && test "$(find "$XDG_CONFIG_HOME/StardewValley/Saves" -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 1 \
 && save_dir="$(find "$XDG_CONFIG_HOME/StardewValley/Saves" -mindepth 1 -maxdepth 1 -type d)" \
 # An interrupted save leaves only a zero-byte *_STARDEWVALLEYSAVETMP file; the
 # fixture is usable only when the named save and SaveGameInfo both exist.
 && test -s "$save_dir/$(basename "$save_dir")" \
 && test -s "$save_dir/SaveGameInfo" \
 && basename "$save_dir" > /opt/gcb/save-name.txt \
 && rm -rf /opt/stardew/Mods/GcbHarness

WORKDIR /app
