# Separate verifier image for one Minecraft (Paper plugin) repair task.
#
# Harbor builds this file from the task's tests/ directory after the agent
# environment has stopped, so the private suites never enter the agent image.
# The base is the locally built, pinned Paper runtime; it is never published.
# The dependency cache is warmed here (network available at build time) from the
# frozen build files, so the verifier itself runs with no network.
FROM gcb-minecraft-paper-verifier:1.21.11-132

USER root
COPY starter /opt/gcb/starter
RUN mkdir -p /opt/gcb/warm-build && cp -a /opt/gcb/starter/. /opt/gcb/warm-build/ && cd /opt/gcb/warm-build && mkdir -p /opt/gradle-cache && printf 'org.gradle.java.installations.auto-download=false\n' > /opt/gradle-cache/gradle.properties && chmod +x ./gradlew 2>/dev/null || true; ./gradlew --no-daemon --console=plain -q dependencies shadowJar test && ./gradlew --offline --no-daemon --console=plain -q clean shadowJar test && cd / && rm -rf /opt/gcb/warm-build
COPY --chmod=755 test.sh /tests/test.sh
COPY verify.py task.json /tests/
COPY suite /tests/suite
COPY seed /tests/seed
RUN mkdir -p /app/plugin /logs
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
