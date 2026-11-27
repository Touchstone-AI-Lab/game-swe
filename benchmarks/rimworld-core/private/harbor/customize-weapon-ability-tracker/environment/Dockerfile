FROM mcr.microsoft.com/dotnet/sdk:8.0.422-bookworm-slim@sha256:63ebabdcde24cc8134304a6f50719cf1e22bb4e9f7148ac4ef967c7680187356 AS builder-runtime

COPY tests/Submission.csproj tests/Support.cs tests/packages.lock.json \
  /opt/rhenium/tests/
COPY tests/Harness/Harness.csproj tests/Harness/Verifier.cs \
  tests/Harness/GeneratedAssertions.cs \
  tests/Harness/packages.lock.json /opt/rhenium/tests/Harness/
COPY tests/build.sh /opt/rhenium/build.sh
RUN dotnet restore /opt/rhenium/tests/Submission.csproj \
      -p:SubmissionRoot=/opt/rhenium/placeholder \
      -p:BaseIntermediateOutputPath=/opt/rhenium/restore/candidate/ \
      --locked-mode \
      --packages /opt/rhenium/nuget \
    && dotnet restore /opt/rhenium/tests/Harness/Harness.csproj \
      -p:CandidateAssembly=/opt/rhenium/placeholder/CWF.dll \
      -p:BaseIntermediateOutputPath=/opt/rhenium/restore/verifier/ \
      --locked-mode \
      --packages /opt/rhenium/nuget \
    && chmod -R a+rX,a-w /opt/rhenium/tests /opt/rhenium/nuget /opt/rhenium/restore \
    && chmod 0555 /opt/rhenium/build.sh
ENV NUGET_PACKAGES=/opt/rhenium/nuget \
    DOTNET_CLI_HOME=/work/dotnet \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    NUGET_XMLDOC_MODE=skip

FROM mcr.microsoft.com/dotnet/sdk:8.0.422-bookworm-slim@sha256:63ebabdcde24cc8134304a6f50719cf1e22bb4e9f7148ac4ef967c7680187356 AS evaluator-runtime

ARG DEBIAN_SNAPSHOT=20260701T000000Z
RUN set -eux; \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/%s bookworm main\n' "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list; \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s bookworm-security main\n' "$DEBIAN_SNAPSHOT" >> /etc/apt/sources.list; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    apt-get -o Acquire::Check-Valid-Until=false update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl libasound2 libgl1 libgl1-mesa-dri libglu1-mesa \
      libgtk-3-0 libnss3 libpulse0 libx11-6 libxcursor1 libxext6 libxi6 \
      libxinerama1 libxrandr2 unzip xauth xvfb; \
    rm -rf /var/lib/apt/lists/*

COPY game-files/ /opt/rimworld/
RUN chmod 0555 /opt/rimworld/RimWorldLinux

RUN set -eux; \
    curl --fail --location --retry 3 \
      https://github.com/pardeike/HarmonyRimWorld/releases/download/v2.4.2.0/HarmonyMod.zip \
      --output /tmp/HarmonyMod.zip; \
    echo '305d014d3ef893909e28ec48615b886c7ebfa3c71b40a45d45bc20bdd4713af1  /tmp/HarmonyMod.zip' | sha256sum --check; \
    unzip -q /tmp/HarmonyMod.zip -d /tmp/harmony; \
    mkdir -p /opt/rhenium/runtime-mods; \
    mv /tmp/harmony/HarmonyMod /opt/rhenium/runtime-mods/Harmony; \
    rm -rf /tmp/HarmonyMod.zip /tmp/harmony

COPY tests/test.sh /opt/rhenium/test.sh
COPY tests/ModMetadata/ /opt/rhenium/ModMetadata/
COPY tests/ModsConfig.xml /opt/rhenium/ModsConfig.xml
RUN chmod 0555 /opt/rhenium/test.sh \
    && chmod -R a+rX,a-w /opt/rimworld /opt/rhenium

ENV SDL_AUDIODRIVER=dummy
WORKDIR /opt/rimworld
