FROM ubuntu@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-venv xvfb libgl1 libgl1-mesa-dri libglu1-mesa \
    libxext6 libxrandr2 libxi6 libxinerama1 libxcursor1 libxxf86vm1 libasound2t64 \
    libudev1 libopenal1 && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/worker
COPY requirements.txt /opt/requirements.txt
RUN /opt/worker/bin/python -m pip install --no-cache-dir --require-hashes -r /opt/requirements.txt
COPY core /opt/source
COPY plugin /opt/source
RUN chmod -R a+rX /opt/source
ENV PYTHONPATH=/opt/source PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
ENTRYPOINT ["/usr/bin/timeout", "--signal=TERM", "--kill-after=10", "1850", "/opt/worker/bin/python", "-m", "rhenium_balatro.container_worker"]
