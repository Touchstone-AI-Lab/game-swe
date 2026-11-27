FROM gcb-l4d2-sourcemod-verifier:23990100-sm1.12.7246

USER root
COPY --chmod=755 test.sh verify.py /tests/
COPY suite.nut /tests/suite.nut
COPY bootstrap.sp /tests/bootstrap.sp
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
