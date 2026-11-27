# Agent-phase container for the controlled study. It holds ordinary text and
# shell tools only: no game, no verifier, no compiler toolchain, no credentials.
# Rhenium and its Python dependencies are bind-mounted read-only at run time.
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

RUN printf '%s\n' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260830T000000Z bookworm main' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260830T000000Z bookworm-security main' \
      > /etc/apt/sources.list \
 && rm -f /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates diffutils file findutils git less lua5.1 patch procps ripgrep \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
