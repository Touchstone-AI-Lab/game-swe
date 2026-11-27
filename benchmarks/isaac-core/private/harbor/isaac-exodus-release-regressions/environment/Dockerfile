FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates curl git jq patch procps python3 ripgrep \
 && rm -rf /var/lib/apt/lists/*

# Pin Claude Code so Harbor's Claude agent can start while trial networking is
# restricted to the model API. No credentials are embedded in the image.
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh \
      | bash -s -- 2.1.226 \
 && install -m 0755 "$(readlink -f /root/.local/bin/claude)" /usr/local/bin/claude \
 && claude --version

# mini-swe-agent is preinstalled because the agent phase is network-allowlisted and
# cannot fetch arbitrary package hosts at runtime.
RUN UV_INSTALL_DIR=/usr/local/bin curl -LsSf https://astral.sh/uv/0.7.13/install.sh \
      | env UV_INSTALL_DIR=/usr/local/bin sh \
 && UV_TOOL_BIN_DIR=/usr/local/bin /usr/local/bin/uv tool install \
      'mini-swe-agent==2.4.6' --with 'litellm[proxy]==1.95.0' \
 && command -v mini-swe-agent >/dev/null

COPY exodus /app/exodus

WORKDIR /app/exodus
