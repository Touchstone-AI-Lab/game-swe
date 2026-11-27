# Separate verifier image. Harbor builds this file from each task's tests/
# directory after the agent environment has stopped, so verifier assertions are
# never copied into the agent image.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

ARG DEBIAN_FRONTEND=noninteractive

RUN printf '%s\n' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260830T000000Z bookworm main' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260830T000000Z bookworm-updates main' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260830T000000Z bookworm-security main' \
      > /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      bash=5.2.15-2+b13 \
      build-essential=12.9 \
      ca-certificates=20250419~deb12u1 \
      python3=3.11.2-1+b1 \
      python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir 'lupa==2.8' \
    && python3 -c 'from lupa.lua54 import LuaRuntime; assert LuaRuntime().eval("_VERSION") == "Lua 5.4"'

RUN mkdir -p /app/mod /tests

COPY --chmod=755 test.sh /tests/test.sh
COPY behavior.lua lua_runner.py server.lua spec.json verify.py /tests/

WORKDIR /app/mod
