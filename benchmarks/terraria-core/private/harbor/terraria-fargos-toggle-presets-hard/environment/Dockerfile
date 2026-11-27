FROM mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim@sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY fargos-souls/ /workspace/fargos-souls/

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    NUGET_XMLDOC_MODE=skip

ENTRYPOINT []
CMD ["sleep", "infinity"]
