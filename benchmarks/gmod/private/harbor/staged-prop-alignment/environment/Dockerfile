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
      curl=7.88.1-10+deb12u15 \
      git=1:2.39.5-0+deb12u3 \
      lua5.1=5.1.5-9 \
      python3=3.11.2-1+b1 \
      python3-pip=23.0.1+dfsg-1 \
      ripgrep=13.0.0-4+b2 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir \
      'litellm==1.98.0' \
      'lupa==2.8' \
      'mini-swe-agent==2.4.6' \
    && npm install --global '@openai/codex@0.153.4' \
    && codex --version \
    && command -v mini >/dev/null

RUN useradd --create-home --shell /bin/bash agent \
    && mkdir -p /app/addon \
    && chown -R agent:agent /app

COPY --chown=agent:agent addon /app/addon

WORKDIR /app/addon
