FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git patch python3 ripgrep \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /bin/bash agent

RUN install -d /opt/sourcemod \
 && curl -fsSL -o /tmp/sourcemod.tar.gz \
      https://github.com/alliedmodders/sourcemod/releases/download/1.12.0.7246/sourcemod-1.12.0-git7246-linux.tar.gz \
 && echo "5f5a7a021ba231e03d6698ae4f0dc8c50fca4884b7f399c892b8e964c4754b1c  /tmp/sourcemod.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/sourcemod.tar.gz -C /opt/sourcemod \
 && rm /tmp/sourcemod.tar.gz \
 && test -x /opt/sourcemod/addons/sourcemod/scripting/spcomp64

RUN curl -LsSf https://astral.sh/uv/0.7.13/install.sh \
      | env UV_INSTALL_DIR=/usr/local/bin sh \
 && UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin \
      /usr/local/bin/uv tool install 'mini-swe-agent==2.4.6' --with 'litellm[proxy]==1.95.0' \
 && chown -R agent:agent /opt/uv-tools \
 && command -v mini-swe-agent >/dev/null

COPY --chown=agent:agent left4dhooks /app/left4dhooks
RUN find /app/left4dhooks -exec touch -h -d '@0' {} +

ENV HOME=/home/agent \
    SP_COMPILER=/opt/sourcemod/addons/sourcemod/scripting/spcomp64 \
    SM_INCLUDE=/opt/sourcemod/addons/sourcemod/scripting/include \
    UV_TOOL_DIR=/opt/uv-tools
WORKDIR /app/left4dhooks
