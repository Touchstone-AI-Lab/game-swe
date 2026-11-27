# Separate verifier image. Harbor builds this file from each task's tests/
# directory after the agent environment has stopped, so the private suites are
# never copied into the agent image. The base is the locally built, pinned
# Don't Starve Together dedicated-server runtime from
# benchmarks/dst/private/runtime/dst-harbor-runtime; it is never published.
FROM gcb-dst-dedicated-verifier:24700372

USER root
COPY --chmod=755 test.sh /tests/test.sh
COPY verify.py /tests/verify.py
COPY pack /tests/pack
RUN mkdir -p /app/mod
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
