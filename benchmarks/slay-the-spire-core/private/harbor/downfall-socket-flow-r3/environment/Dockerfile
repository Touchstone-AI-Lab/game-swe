FROM sha256:9f737c92646e7d4735f81a69af53b1e5a0fe2e225c4f13b758232de6e511b750
WORKDIR /app/downfall
COPY project/ ./
RUN bash build.sh && rm -rf target && git init && git config user.email benchmark@localhost && git config user.name Benchmark && git add . && git commit -m "Task starting state"
