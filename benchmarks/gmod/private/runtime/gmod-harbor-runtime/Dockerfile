# Shared, verifier-only Garry's Mod Addons runtime. This directory is
# infrastructure, not a benchmark task. No Facepunch or Valve files are committed
# to the repository: the pinned Dedicated Server comes from the operator's own
# retained installation through the named `server` build context, and the
# resulting image is local and non-redistributable. Build it with build-image.sh.
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG GMOD_BUILD_ID=23150012

# srcds_linux is a 32-bit x86 ELF and needs the i386 loader and libraries.
RUN dpkg --add-architecture i386 \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates procps util-linux \
      lib32gcc-s1 lib32stdc++6 libc6-i386 \
      libtinfo6:i386 libncurses6:i386 zlib1g:i386 \
      python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/verifier/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir -r /opt/verifier/requirements.txt

# The server and the evaluator's writable state must share one filesystem: the
# native runner builds each per-phase server view from hard links.
COPY --from=server / /opt/gmod/server
RUN grep -Eq "\"buildid\"[[:space:]]+\"${GMOD_BUILD_ID}\"" /opt/gmod/server/steamapps/appmanifest_4020.acf \
 && test -x /opt/gmod/server/srcds_linux \
 && install -d -m 0777 /opt/gmod/state

# The evaluator is the repository's own Garry's Mod plugin, vendored
# byte-for-byte by private/harbor/scripts/materialize.py so a Harbor reward is
# the Rhenium full-profile verdict rather than a reimplementation of it.
COPY evaluator /opt/verifier/python
RUN /opt/verifier-venv/bin/python -c \
      "import sys; sys.path.insert(0, '/opt/verifier/python'); import rhenium_garrys_mod.addons.evaluator"

ENV RHENIUM_PLUGIN_GMOD_SERVER_ROOT=/opt/gmod/server \
    RHENIUM_PLUGIN_GMOD_GLOBAL_TIMEOUT=900 \
    PYTHONPATH=/opt/verifier/python \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/verifier-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /app
