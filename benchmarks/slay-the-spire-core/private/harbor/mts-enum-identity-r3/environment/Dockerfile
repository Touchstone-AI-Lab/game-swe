FROM sha256:233e1d8f96e8368fa753bdcb6730de724f482e865beb2241a05b412fcfe6c350
WORKDIR /app/modthespire
COPY project/ ./
RUN MAVEN_OPTS=-Xmx512m mvn -B -o clean test package && cp target/ModTheSpire.jar /opt/sts/lib/ModTheSpire.jar && rm -rf target && rm -f dependency-reduced-pom.xml && git init && git config user.email benchmark@localhost && git config user.name Benchmark && git add . && git commit -m "Task starting state"
