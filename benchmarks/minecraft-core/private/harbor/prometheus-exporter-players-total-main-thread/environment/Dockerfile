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
RUN mkdir -p /opt/maven && python3 -c "import hashlib, sys, urllib.request; data = urllib.request.urlopen('https://archive.apache.org/dist/maven/maven-3/3.9.11/binaries/apache-maven-3.9.11-bin.tar.gz', timeout=300).read(); sys.exit('maven checksum mismatch') if hashlib.sha512(data).hexdigest() != 'bcfe4fe305c962ace56ac7b5fc7a08b87d5abd8b7e89027ab251069faebee516b0ded8961445d6d91ec1985dfe30f8153268843c89aa392733d1a3ec956c9978' else None; open('/tmp/maven.tgz', 'wb').write(data)" && tar -xzf /tmp/maven.tgz -C /opt/maven --strip-components=1 && rm -f /tmp/maven.tgz && ln -s /opt/maven/bin/mvn /usr/local/bin/mvn && mvn -v
RUN cd /app/plugin && mkdir -p /opt/m2 && chmod +x mvn 2>/dev/null || true; mvn -B -q -Dmaven.repo.local=/opt/m2 dependency:go-offline test && mvn -o -B -q -Dmaven.repo.local=/opt/m2 clean test package
RUN chown -R agent:agent /app /opt/gradle-cache /opt/m2 2>/dev/null || true
USER agent
CMD ["sleep", "infinity"]
