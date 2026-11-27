FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git patch python3 ripgrep \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /bin/bash agent

RUN curl -LsSf https://astral.sh/uv/0.7.13/install.sh \
      | env UV_INSTALL_DIR=/usr/local/bin sh \
 && UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin \
      /usr/local/bin/uv tool install 'mini-swe-agent==2.4.6' --with 'litellm[proxy]==1.95.0' \
 && chown -R agent:agent /opt/uv-tools \
 && command -v mini-swe-agent >/dev/null

COPY --chown=agent:agent linge-hud /app/linge-hud

ENV HOME=/home/agent \
    UV_TOOL_DIR=/opt/uv-tools
WORKDIR /app/linge-hud
