FROM mindustry

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash python3 && \
    rm -rf /var/lib/apt/lists/*

COPY . /tests/
ENTRYPOINT []
CMD ["sleep", "infinity"]
