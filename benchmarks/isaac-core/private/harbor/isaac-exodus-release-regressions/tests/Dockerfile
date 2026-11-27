FROM gcb-isaac-private-runtime:abp-v1.06.t1

USER root

COPY --chmod=755 test.sh run-game.sh /tests/
COPY suite /tests/suite
COPY secret-suite /tests/secret-suite
COPY james-suite /tests/james-suite

WORKDIR /app
