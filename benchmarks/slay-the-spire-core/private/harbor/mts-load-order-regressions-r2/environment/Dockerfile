FROM sha256:233e1d8f96e8368fa753bdcb6730de724f482e865beb2241a05b412fcfe6c350
WORKDIR /app/modthespire
COPY project/ ./
# The agent environment keeps r1's offline Maven contract: the starter's own `clean test`
# runs offline against the pinned public cache. A throwaway test proves the JUnit provider
# resolves without network; it is removed again so the starter tree is unchanged.
RUN mkdir -p src/test/java/warm \
 && printf 'package warm;\nimport org.junit.jupiter.api.Test;\npublic class WarmTest { @Test public void t() { } }\n' > src/test/java/warm/WarmTest.java \
 && MAVEN_OPTS=-Xmx512m mvn -B -o -q clean test -Dtest=WarmTest \
 && rm -rf src/test target \
 && echo "offline maven verified"
