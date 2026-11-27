# Pinned Paper dedicated-server verifier base image.
#
# Built locally by `rhenium runtime prepare minecraft/paper-1.21.11-132` from a
# staged context: the server jar downloaded by the official-download provider
# (SHA-256 pinned by the runtime catalog), the operator's own EULA acceptance
# record, this pack's runtime assets and the GcbHarness sources. The paperclip
# bootstrap needs network once (it downloads the Mojang server jar); every
# evaluation container then runs with no network. The resulting image contains
# Mojang code and is never published.
FROM eclipse-temurin:21-jdk@sha256:92a2a4d7a928d057e7bd999c418d66c26a34eb9a0442f3ab67721c3f88110b2d

ENV DEBIAN_FRONTEND=noninteractive \
    GRADLE_USER_HOME=/opt/gradle-cache \
    MAVEN_OPTS=-Dmaven.repo.local=/opt/m2 \
    GCB_PAPER=/opt/paper \
    GCB_HOME=/opt/gcb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates git patch python3 rsync unzip \
    && rm -rf /var/lib/apt/lists/*

COPY paper-1.21.11-132.jar eula.txt /opt/paper/
COPY runtime/ /opt/gcb/runtime/
COPY gcb-harness/ /opt/gcb/harness/src/

RUN bash /opt/gcb/runtime/bootstrap.sh

WORKDIR /app
