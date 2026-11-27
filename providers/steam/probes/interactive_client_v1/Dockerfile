# Local, non-redistributable capability probe. No client or account state in image.
# Keep the base from the reviewed provider recipe; packages are container-local.
FROM ubuntu:24.04@sha256:69cecf4bbf72d2d44a9eef1b71fb98c7fb973d78af11399deccef19beb008ad9
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's/^Components: main restricted$/Components: main restricted universe multiverse/' /etc/apt/sources.list.d/ubuntu.sources \
 && dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates coreutils curl dbus-user-session dbus-x11 findutils \
      fontconfig fonts-dejavu-core locales procps tar xz-utils \
      libasound2t64 libasound2t64:i386 libgl1 libgl1:i386 libgl1-mesa-dri libgl1-mesa-dri:i386 \
      libglu1-mesa libopenal1 libopenal1:i386 libstdc++6:i386 libudev1:i386 \
      libx11-6:i386 libxcursor1:i386 libxext6:i386 libxi6:i386 libxinerama1:i386 \
      libxrandr2:i386 libxss1:i386 libxtst6:i386 \
 && locale-gen en_US.UTF-8 \
 && rm -rf /var/lib/apt/lists/*
ENV LANG=en_US.UTF-8
# This bounded probe is for the already-verified WSL uid/gid 1000 only.
RUN usermod --login steamprobe --home /home/steamprobe --move-home ubuntu \
 && groupmod --new-name steamprobe ubuntu \
 && install -d -m 1777 /tmp/.X11-unix
COPY launch.sh /opt/steam-probe/launch.sh
RUN chmod 0555 /opt/steam-probe/launch.sh
USER 1000:1000
ENTRYPOINT ["/opt/steam-probe/launch.sh"]
