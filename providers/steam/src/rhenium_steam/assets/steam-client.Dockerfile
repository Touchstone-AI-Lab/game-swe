# Headless official Steam client used by `rhenium auth login steam` to bootstrap the client
# state that DRM-protected runtimes need in order to start their game offline.
#
# The image carries only the operating system packages. The Steam client itself is installed
# into the operator's mounted client home at run time from the version pinned in
# steam-client-session.sh, so the image never contains Valve's client or any account state.
FROM ubuntu:24.04@sha256:69cecf4bbf72d2d44a9eef1b71fb98c7fb973d78af11399deccef19beb008ad9

ENV DEBIAN_FRONTEND=noninteractive

# universe/multiverse carry the 32-bit runtime libraries the client and its games require.
RUN sed -i 's/^Components: main restricted$/Components: main restricted universe multiverse/' \
      /etc/apt/sources.list.d/ubuntu.sources \
 && dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates coreutils curl dbus-user-session dbus-x11 findutils fontconfig \
      locales procps tar xz-utils \
      openbox xauth xdotool xvfb x11-utils imagemagick zbar-tools \
      libasound2t64 libasound2t64:i386 libgl1 libgl1:i386 libgl1-mesa-dri libgl1-mesa-dri:i386 \
      libglu1-mesa libopenal1 libopenal1:i386 libstdc++6:i386 libudev1:i386 \
      libx11-6:i386 libxcursor1:i386 libxext6:i386 libxi6:i386 libxinerama1:i386 \
      libxrandr2:i386 libxss1:i386 libxtst6:i386 \
 && locale-gen en_US.UTF-8 \
 && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8

# The provider runs this container as the operator's uid:gid with HOME=/home/azureuser and
# mounts only $HOME/.steam into it, so the home directory itself must already exist in the
# image and be writable by that user. Without it the client cannot create ~/.steampath,
# ~/.cache or ~/.config and stops at an error dialog before it ever shows a sign-in QR code.
#
# Renaming ubuntu only satisfies that when the operator happens to be uid 1000, which is the
# case on a single-user desktop but not on a shared or domain-joined host. On a cluster
# account (uid 300028) two things broke: /home/azureuser stayed owned by 1000 and mode 0750,
# so installing the client failed with "cannot create directory"; and the running uid had no
# /etc/passwd entry at all, so dbus reported `User "???" unknown` and refused to start the
# message bus the client depends on. Both are fixed by pointing the account at the
# operator's real ids at build time -- chmod alone grants write access but does not make the
# user exist.
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN usermod --login azureuser --home /home/azureuser --move-home ubuntu \
 && groupmod --new-name azureuser ubuntu \
 && if [ "${HOST_GID}" != "1000" ]; then groupmod -g "${HOST_GID}" azureuser; fi \
 && if [ "${HOST_UID}" != "1000" ]; then usermod -u "${HOST_UID}" -g "${HOST_GID}" azureuser; fi \
 && chown -R "${HOST_UID}:${HOST_GID}" /home/azureuser

COPY steam-client-session.sh /opt/rhenium/steam-client-session.sh

ENTRYPOINT ["/opt/rhenium/steam-client-session.sh"]
