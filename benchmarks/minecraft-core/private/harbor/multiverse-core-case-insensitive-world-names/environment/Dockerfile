# Agent environment for one Minecraft (Paper plugin) repair task.
#
# JDK 21, the repository's build tool with its dependency cache warmed while the
# image is built, and the starter tree. No Paper server: the agent can compile
# and run the repository's own tests, not the game. The verifier image is
# separate and holds the pinned server.
FROM eclipse-temurin:21-jdk@sha256:92a2a4d7a928d057e7bd999c418d66c26a34eb9a0442f3ab67721c3f88110b2d

ENV DEBIAN_FRONTEND=noninteractive \
    GRADLE_USER_HOME=/opt/gradle-cache \
    MAVEN_OPTS=-Dmaven.repo.local=/opt/m2 \
    HOME=/home/agent

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates curl git patch python3 python3-pip ripgrep rsync unzip \
    && rm -rf /var/lib/apt/lists/* \
    && (userdel --remove ubuntu 2>/dev/null || true) \
    && useradd --create-home --uid 1000 agent \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        litellm==1.98.0 mini-swe-agent==2.4.6

COPY plugin /app/plugin
WORKDIR /app/plugin
RUN cd /app/plugin && mkdir -p /opt/gradle-cache && printf 'org.gradle.java.installations.auto-download=false\n' > /opt/gradle-cache/gradle.properties && chmod +x ./gradlew 2>/dev/null || true; ./gradlew --no-daemon --console=plain -q dependencies shadowJar test && ./gradlew --offline --no-daemon --console=plain -q clean shadowJar test
RUN chown -R agent:agent /app /opt/gradle-cache /opt/m2 2>/dev/null || true
USER agent
CMD ["sleep", "infinity"]
