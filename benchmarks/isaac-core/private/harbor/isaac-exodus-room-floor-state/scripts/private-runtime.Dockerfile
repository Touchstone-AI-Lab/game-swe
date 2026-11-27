# syntax=docker/dockerfile:1.7

# These are local BuildKit named contexts supplied by prepare-private-runtime.sh.
FROM steam_home AS steam_home_source
FROM isaac_data AS isaac_data_source

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates coreutils curl dbus-user-session dbus-x11 findutils \
      fontconfig gawk grep locales openbox procps sed tar util-linux xauth xdotool \
      xvfb xz-utils zenity \
      libasound2t64 libasound2t64:i386 libgl1 libgl1:i386 \
      libgl1-mesa-dri libgl1-mesa-dri:i386 libglu1-mesa \
      libopenal1 libopenal1:i386 libstdc++6:i386 libudev1:i386 \
      libx11-6:i386 libxcursor1:i386 libxext6:i386 libxi6:i386 \
      libxinerama1:i386 libxrandr2:i386 libxss1:i386 libxtst6:i386 \
 && rm -rf /var/lib/apt/lists/*

RUN if id -u ubuntu >/dev/null 2>&1; then \
      usermod --login azureuser --home /home/azureuser --move-home ubuntu \
      && groupmod --new-name azureuser ubuntu; \
    else \
      useradd --create-home --uid 1000 --shell /bin/bash azureuser; \
    fi

COPY --from=steam_home_source --chown=1000:1000 / /home/azureuser/.steam/
COPY --from=isaac_data_source --chown=1000:1000 ["/", "/home/azureuser/.local/share/binding of isaac afterbirth+/"]

RUN unlink /home/azureuser/.steam/steam.pid 2>/dev/null || true \
 && unlink /home/azureuser/.steam/steam.pipe 2>/dev/null || true \
 && unlink /home/azureuser/.steam/steam.token 2>/dev/null || true \
 && install -d -o 1000 -g 1000 -m 0755 \
      /home/azureuser/.cache \
      /home/azureuser/.config \
      "/home/azureuser/.local/share/binding of isaac afterbirth+ mods"

ENV HOME=/home/azureuser \
    DISPLAY=:99 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    GDK_BACKEND=x11 \
    SDL_VIDEODRIVER=x11 \
    XDG_RUNTIME_DIR=/tmp/steam-runtime-azureuser

USER azureuser
WORKDIR /home/azureuser
CMD ["bash"]
