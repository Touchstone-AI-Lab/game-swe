# Pinned Mindustry dedicated-server verifier base image.
#
# Built locally by `rhenium runtime prepare mindustry/mindustry-159.7` from a staged
# context that holds the server-release.jar downloaded by the official-download
# provider (SHA-256 pinned by the runtime catalog) next to this pack's runtime scripts
# and the trusted Rhenium harness sources. Package installation needs network once, at
# preparation; every evaluation container then runs with no network. The image is
# local and never published.
FROM eclipse-temurin:17-jdk@sha256:bc033b57e11b773c3043babfd664e7a5ef110805548b921cbfc3e8c67a0725d6

ENV DEBIAN_FRONTEND=noninteractive \
    RHENIUM_MINDUSTRY=/opt/mindustry \
    RHENIUM_HOME=/opt/rhenium

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash python3 rsync unzip \
    && rm -rf /var/lib/apt/lists/*

COPY server-release.jar /opt/mindustry/server-release.jar
COPY runtime/ /opt/rhenium/runtime/
COPY rhenium-harness/ /opt/rhenium/harness/src/

RUN bash /opt/rhenium/runtime/bootstrap.sh

WORKDIR /app
