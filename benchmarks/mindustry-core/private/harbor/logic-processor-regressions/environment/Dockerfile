# Agent environment for one Mindustry (game source) repair task.
#
# JDK 17 and the starter tree. No Mindustry server: the agent can read and edit
# the sources, not run the game. The verifier image is separate and holds the
# pinned server.
FROM eclipse-temurin:17-jdk@sha256:bc033b57e11b773c3043babfd664e7a5ef110805548b921cbfc3e8c67a0725d6

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/agent

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git patch python3 python3-pip ripgrep rsync unzip \
    && rm -rf /var/lib/apt/lists/* \
    && (userdel --remove ubuntu 2>/dev/null || true) \
    && useradd --create-home --uid 1000 agent \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        litellm==1.98.0 mini-swe-agent==2.4.6

COPY mindustry /app/mindustry
WORKDIR /app/mindustry
RUN chown -R agent:agent /app
USER agent
CMD ["sleep", "infinity"]
