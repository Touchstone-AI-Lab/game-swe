# Pinned by digest: Maven 3.9 on Eclipse Temurin JDK 8. ModTheSpire is a Java 8 project
# and does not compile on 17 (it uses sun.misc / sun.reflect internals).
FROM maven:3.9-eclipse-temurin-8@sha256:d8b1b22e93012cd0257d37b3fd6d7bec3d0f7ae611730fc3ba0657b9ebe4e7ca

WORKDIR /app
COPY modthespire /app/modthespire

# Warm the Maven repository at build time so the verifier can run fully offline.
#
# The warm-up runs the EXACT goals the verifier runs (`clean test`). Anything less leaves
# a plugin unresolved: Surefire fetches its JUnit provider only when a test really runs,
# and maven-clean-plugin is only fetched when `clean` is invoked. Warming a subset of the
# goals silently produces an image that fails offline at scoring time.
#
# The second, offline invocation is an assertion: if the cache were incomplete this fails
# the image build rather than a scored run.
RUN cd /app/modthespire \
 && mkdir -p src/test/java/warm \
 && printf 'package warm;\nimport org.junit.jupiter.api.Test;\npublic class WarmTest { @Test public void t() { } }\n' > src/test/java/warm/WarmTest.java \
 && mvn -B -q clean test -Dtest=WarmTest \
 && mvn -B -o -q clean test -Dtest=WarmTest \
 && rm -rf src/test/java/warm target \
 && echo "offline maven verified"

WORKDIR /app/modthespire
