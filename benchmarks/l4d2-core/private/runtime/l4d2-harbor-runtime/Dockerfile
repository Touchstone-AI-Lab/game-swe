# Shared, verifier-only Left 4 Dead 2 runtime. This directory is infrastructure,
# not a benchmark task. No Valve files are committed to the repository.
FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG L4D2_BUILD_ID=23990100
ARG SOURCEMOD_VERSION=1.12.0-git7246
ARG METAMOD_VERSION=1.12.0-git1225

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl python3 python3-pip procps util-linux \
      lib32gcc-s1 lib32stdc++6 libc6-i386 \
      libtinfo6:i386 libncurses6:i386 zlib1g:i386 \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir 'vpk==1.4.0' \
 && python3 -c 'import vpk; print(vpk.__version__ if hasattr(vpk, "__version__") else "vpk-1.4.0")'

RUN useradd --create-home --shell /bin/bash steam \
 && install -d -o steam -g steam /opt/steamcmd /opt/l4d2

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
RUN bash ./install-server.sh /opt/steamcmd/steamcmd.sh /opt/l4d2 "$L4D2_BUILD_ID"

USER root
RUN (curl --http1.1 --retry 2 --retry-all-errors --connect-timeout 30 --max-time 120 -fsSL \
      -o /tmp/sourcemod.tar.gz \
      "https://sm.alliedmods.net/smdrop/1.12/sourcemod-${SOURCEMOD_VERSION}-linux.tar.gz" \
   || curl --http1.1 --retry 5 --retry-all-errors --connect-timeout 30 --max-time 300 -fsSL \
      -o /tmp/sourcemod.tar.gz \
      "https://github.com/alliedmodders/sourcemod/releases/download/${SOURCEMOD_VERSION/-git/.}/sourcemod-${SOURCEMOD_VERSION}-linux.tar.gz") \
 && echo "5f5a7a021ba231e03d6698ae4f0dc8c50fca4884b7f399c892b8e964c4754b1c  /tmp/sourcemod.tar.gz" | sha256sum -c - \
 && curl --http1.1 --retry 5 --retry-all-errors --connect-timeout 30 --max-time 300 -fsSL \
      -o /tmp/metamod.tar.gz \
      "https://www.metamodsource.net/mmsdrop/1.12/mmsource-${METAMOD_VERSION}-linux.tar.gz" \
 && echo "9291c702be728ae3010f33c3c671b4d9cdc2cf743d4427d79c92f303ef48be74  /tmp/metamod.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/sourcemod.tar.gz -C /opt/l4d2/left4dead2 \
 && tar -xzf /tmp/metamod.tar.gz -C /opt/l4d2/left4dead2 \
 && rm /tmp/sourcemod.tar.gz /tmp/metamod.tar.gz \
 && rm -f /opt/l4d2/left4dead2/addons/metamod_x64.vdf \
 && find /opt/l4d2/left4dead2/addons/sourcemod/plugins -type f -name '*.smx' -delete \
 && test -x /opt/l4d2/srcds_run \
 && test -x /opt/l4d2/left4dead2/addons/sourcemod/scripting/spcomp64 \
 && chown -R steam:steam /opt/l4d2 \
 && chmod -R go-w /opt/l4d2

COPY --chown=steam:steam metamod.vdf /opt/l4d2/left4dead2/addons/metamod.vdf

ENV L4D2_ROOT=/opt/l4d2 \
    SOURCEMOD_ROOT=/opt/l4d2/left4dead2/addons/sourcemod \
    SteamAppId=550
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
