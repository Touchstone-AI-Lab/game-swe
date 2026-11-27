FROM sha256:233e1d8f96e8368fa753bdcb6730de724f482e865beb2241a05b412fcfe6c350
WORKDIR /app/basemod
COPY project/ ./
RUN mvn -B -o clean test package -pl mod -am && cp mod/target/BaseMod.jar /opt/sts/lib/BaseMod.jar && rm -rf mod/target target && git init && git config user.email benchmark@localhost && git config user.name Benchmark && git add . && git commit -m "Task starting state"
