FROM maven@sha256:e20e4fc05fb5480c884a1f750c362ed0e91aca15cec5736e12796713710ec9b3
LABEL org.opencontainers.image.title="SWE-Game Slay the Spire public tools" \
      org.opencontainers.image.description="Java 8, Maven and pinned Linux graphics tools; no game or benchmark task payloads" \
      org.opencontainers.image.source="https://github.com/Touchstone-AI-Lab/SWE-Game" \
      org.opencontainers.image.url="https://github.com/Touchstone-AI-Lab/SWE-Game/tree/main/benchmarks/slay-the-spire-core/private/native-runtime"
COPY packages/ /opt/runtime-packages/
COPY runtime-packages.tsv /opt/sts/provenance/expected-packages.tsv
RUN cd /opt/runtime-packages \
 && sha256sum -c packages.sha256 \
 && apt-get install -y --no-install-recommends /opt/runtime-packages/*.deb \
 && dpkg-query -W > /opt/sts/provenance/actual-packages.tsv \
 && diff -u /opt/sts/provenance/expected-packages.tsv /opt/sts/provenance/actual-packages.tsv \
 && rm -rf /opt/runtime-packages
ENV LIBGL_ALWAYS_SOFTWARE=1
WORKDIR /opt/sts
