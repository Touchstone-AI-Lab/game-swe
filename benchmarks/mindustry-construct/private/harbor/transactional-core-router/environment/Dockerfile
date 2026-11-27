FROM mindustry:159.7

WORKDIR /workspace/mindustry

RUN apt-get update && \
    apt-get install -y --no-install-recommends bash python3 && \
    rm -rf /var/lib/apt/lists/*

COPY mindustry/ /workspace/mindustry/

ENTRYPOINT []
CMD ["sleep", "infinity"]
