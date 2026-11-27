# Separate verifier image for one Minecraft (Paper plugin) construct task.
#
# Harbor builds this file from the task's tests/ directory after the agent
# environment has stopped, so the private suites never enter the agent image.
# The base is the locally built, pinned Paper runtime; it is never published.
# The dependency cache is warmed here (network available at build time) from the
# frozen build files, so the verifier itself runs with no network.
FROM gcb-minecraft-paper-verifier:1.21.11-132

USER root
RUN mkdir -p /root/.m2 && printf '%s\n' \
    '<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0">' \
    '  <mirrors>' \
    '    <mirror>' \
    '      <id>huaweicloud-maven-central</id>' \
    '      <mirrorOf>central</mirrorOf>' \
    '      <url>https://repo.huaweicloud.com/repository/maven/</url>' \
    '    </mirror>' \
    '  </mirrors>' \
    '</settings>' > /root/.m2/settings.xml
COPY starter /opt/gcb/starter
RUN mkdir -p /opt/maven && python3 -c "import hashlib, sys, urllib.request; data = urllib.request.urlopen('https://repo.huaweicloud.com/apache/maven/maven-3/3.9.11/binaries/apache-maven-3.9.11-bin.tar.gz', timeout=300).read(); sys.exit('maven checksum mismatch') if hashlib.sha512(data).hexdigest() != 'bcfe4fe305c962ace56ac7b5fc7a08b87d5abd8b7e89027ab251069faebee516b0ded8961445d6d91ec1985dfe30f8153268843c89aa392733d1a3ec956c9978' else None; open('/tmp/maven.tgz', 'wb').write(data)" && tar -xzf /tmp/maven.tgz -C /opt/maven --strip-components=1 && rm -f /tmp/maven.tgz && ln -s /opt/maven/bin/mvn /usr/local/bin/mvn && mvn -v
RUN mkdir -p /opt/gcb/warm-build && cp -a /opt/gcb/starter/. /opt/gcb/warm-build/ && cd /opt/gcb/warm-build && mkdir -p /opt/m2 && chmod +x mvn 2>/dev/null || true; mvn -B -q -Dmaven.repo.local=/opt/m2 dependency:go-offline -DskipTests && mvn -o -B -q -Dmaven.repo.local=/opt/m2 clean -DskipTests package && cd / && rm -rf /opt/gcb/warm-build
COPY --chmod=755 test.sh /tests/test.sh
COPY verify.py task.json /tests/
COPY suite /tests/suite
RUN mkdir -p /app/plugin /logs
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
