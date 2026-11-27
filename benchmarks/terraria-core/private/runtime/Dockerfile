FROM mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim@sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    NUGET_XMLDOC_MODE=skip \
    TML_STEAM_PATH=/opt/tmodloader

COPY tmodloader/ /opt/tmodloader/
COPY packages/ /opt/nuget-source/
COPY runtime/run-verifier.sh /usr/local/bin/gcb-terraria-verifier

RUN groupadd --gid 10001 gcb \
 && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/gcb gcb \
 && install -d -o gcb -g gcb /opt/tmodloader/tModLoader-Logs /workspace /state /reports \
 && chmod 0755 /usr/local/bin/gcb-terraria-verifier

USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/gcb-terraria-verifier"]
