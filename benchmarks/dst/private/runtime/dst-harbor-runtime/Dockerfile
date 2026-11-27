# Shared, verifier-only Don't Starve Together runtime. This directory is
# infrastructure, not a benchmark task. No Klei files are committed to the
# repository: the dedicated server is downloaded anonymously at build time and
# the resulting image is local and non-redistributable.
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG DST_BUILD_ID=24700372

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl procps util-linux \
      lib32gcc-s1 lib32stdc++6 libc6-i386 \
      libcurl3t64-gnutls libgcc-s1 libstdc++6 \
      python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash steam \
 && install -d -o steam -g steam /opt/steamcmd /opt/dst

USER steam
WORKDIR /opt/steamcmd
RUN curl --http1.1 --retry 5 --retry-all-errors --connect-timeout 30 --max-time 300 -fsSL \
      -o /tmp/steamcmd_linux.tar.gz \
      https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
 && echo "cebf0046bfd08cf45da6bc094ae47aa39ebf4155e5ede41373b579b8f1071e7c  /tmp/steamcmd_linux.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/steamcmd_linux.tar.gz \
 && rm /tmp/steamcmd_linux.tar.gz

# Cache the client bootstrap separately from the much larger server download.
RUN ./steamcmd.sh +quit
COPY --chown=steam:steam install-server.sh /opt/steamcmd/install-server.sh
RUN bash ./install-server.sh /opt/steamcmd/steamcmd.sh /opt/dst "$DST_BUILD_ID"

USER root
COPY requirements.txt /opt/verifier/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir -r /opt/verifier/requirements.txt

# The evaluator is the repository's own DST plugin, vendored byte-for-byte by
# private/harbor/scripts/materialize.py so a Harbor reward is the Rhenium
# full-profile verdict rather than a reimplementation of it.
COPY evaluator /opt/verifier/python
RUN /opt/verifier-venv/bin/python -c \
      "import sys; sys.path.insert(0, '/opt/verifier/python'); import rhenium_dst.evaluator"

# The dedicated server copies each submission under its mods directory.
RUN chmod -R a+rwX /opt/dst/mods

ENV DST_ROOT=/opt/dst \
    RHENIUM_PLUGIN_DST_ROOT=/opt/dst \
    PYTHONPATH=/opt/verifier/python \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/verifier-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /app
