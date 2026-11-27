FROM sha256:233e1d8f96e8368fa753bdcb6730de724f482e865beb2241a05b412fcfe6c350
WORKDIR /app/stslib
COPY project/ ./
RUN mvn -B -o clean test package && cp target/StSLib.jar /opt/sts/lib/StSLib.jar && rm -rf target && git init && git config user.email benchmark@localhost && git config user.name Benchmark && git add . && git commit -m "Task starting state"
