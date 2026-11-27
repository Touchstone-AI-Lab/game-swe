# Separate verifier image. Harbor builds this file from each task's tests/
# directory after the agent environment has stopped, so the private suites are
# never copied into the agent image. The base is the locally built, pinned
# Garry's Mod Dedicated Server runtime from
# benchmarks/gmod/private/runtime/gmod-harbor-runtime; it is never published.
FROM gcb-gmod-addons-verifier:23150012

USER root
COPY --chmod=755 test.sh /tests/test.sh
COPY verify.py /tests/verify.py
COPY pack /tests/pack
RUN mkdir -p /app/addon
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
