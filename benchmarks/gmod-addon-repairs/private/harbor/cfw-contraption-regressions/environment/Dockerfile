# Self-contained GameCodeBench environment: Garry's Mod dedicated server + GLuaTest.
# The addon under repair is installed by the verifier as a server addon; the sandbox
# gamemode that ships with the server is the host gamemode.
#
# The upstream gluatest image is docker-slim'd (no mkdir, no apt-get, no Python
# shutil), which makes it unusable as a Harbor task base -- the verifier cannot
# stage files or write its reward. We keep its working server tree but rebase it
# onto debian so verifier scripts have ordinary coreutils. rsync in particular is
# required: without it the verifier's override copy fails silently, zero tests run,
# and every submission scores 1.0.
#
# build-essential and git are baked in deliberately: the agent harness runs
#   apt-get update && apt-get install -y curl build-essential git
# as a setup step inside the container, which fails under network_mode=no-network
# and aborts the whole trial. Pre-installing them lets the task run fully isolated.
# Pinned by digest: a floating tag makes a trial irreproducible.
FROM ghcr.io/cfc-servers/gluatest/x86-64@sha256:23cd97d4fa9cf44fc16cabed6b973e117581769725b5735c533d10da7fe0b1fb AS gmod

FROM ghcr.io/astral-sh/uv@sha256:67b30cdbbf9098ede88f38eecde708ddc5aeff3866481b6cb069ae31057f0d63 AS uv

FROM debian@sha256:5ae3c39ebd15e229dcedd5cee596b2497182493d41ff162e824ba13fc1b2b867
RUN printf '%s\n' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260830T000000Z bookworm main' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260830T000000Z bookworm-updates main' \
      'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260830T000000Z bookworm-security main' \
      > /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates=20250419~deb12u1 curl=7.88.1-10+deb12u15 python3=3.11.2-1+b1 \
      lib32gcc-s1=12.2.0-14+deb12u1 lib32stdc++6=12.2.0-14+deb12u1 \
      libncurses6=6.4-4 libtinfo6=6.4-4 expect=5.45.4-2+b1 \
      tar=1.34+dfsg-1.2+deb12u1 gzip=1.12-1 patch=2.7.6-7 \
      rsync=3.2.7-1+deb12u6 build-essential=12.9 git=1:2.39.5-0+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gmod /home/steam /home/steam
COPY --from=uv /uv /usr/local/bin/uv
COPY agent-constraints.txt /opt/rhenium/agent-constraints.txt

ENV HOME=/home/steam
WORKDIR /app

# Pre-install the agent harness at build time so Harbor setup needs no network.
# uv comes from an amd64 manifest digest instead of a remote installer script, and
# the Linux/Python 3.11 dependency closure is constrained in a reviewed file.
RUN UV_TOOL_BIN_DIR=/usr/local/bin UV_PYTHON_DOWNLOADS=never \
      /usr/local/bin/uv tool install \
      --python /usr/bin/python3 --no-managed-python \
      --constraints /opt/rhenium/agent-constraints.txt \
      --exclude-newer 2026-08-30T00:00:00Z \
      --with 'litellm[proxy]==1.98.0' 'mini-swe-agent==2.4.6' \
 && /usr/local/bin/uv --version \
 && command -v mini-swe-agent

COPY cfw /app/cfw
