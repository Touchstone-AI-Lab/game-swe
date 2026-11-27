FROM gcb-l4d2-sourcemod-verifier:23990100-sm1.12.7246

USER root
COPY --chmod=755 test.sh verify.py /tests/
COPY source-manifest.txt /tests/
COPY public_api_consumer.sp /tests/
COPY suite_*.sp /tests/
COPY include /tests/include
COPY fixtures /tests/fixtures
COPY runtime /tests/runtime
COPY deps /tests/deps
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
