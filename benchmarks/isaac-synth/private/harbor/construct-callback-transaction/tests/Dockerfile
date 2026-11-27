ARG PRIVATE_IMAGE
FROM ${PRIVATE_IMAGE}

USER root

COPY --chmod=755 test.sh run-game.sh /tests/
COPY suite /tests/suite

WORKDIR /app
