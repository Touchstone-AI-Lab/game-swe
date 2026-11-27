FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS compiler
ENV DEBIAN_FRONTEND=noninteractive CARGO_HOME=/opt/cargo RUSTUP_HOME=/opt/rustup
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl cmake ninja-build pkg-config gcc g++ git python3 patch \
    libx11-dev libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev \
    libgl-dev libegl-dev libgles-dev && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 3 https://static.rust-lang.org/rustup/archive/1.29.2/x86_64-unknown-linux-gnu/rustup-init \
    -o /tmp/rustup-init \
    && echo '5be191e8c70a5007074254cb74d78dbfdd25cd5a61c27de7b8e5410122ec24f4  /tmp/rustup-init' | sha256sum -c - \
    && chmod +x /tmp/rustup-init && /tmp/rustup-init -y --profile minimal --no-modify-path --default-toolchain 1.90.0
ENV PATH=/opt/cargo/bin:$PATH
COPY recipe/fetch.py recipe/dependencies.json /recipe/
RUN python3 /recipe/fetch.py
RUN cmake -S /source -B /build -G Ninja -DCMAKE_BUILD_TYPE=Game__Dev__Linux64 \
    -DUE4SS_GUI_ENABLED=ON -DUE4SS_INPUT_ENABLED=OFF -DUE4SS_PROFILERS=OFF \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DFETCHCONTENT_SOURCE_DIR_GLAZE=/deps/glaze \
    -DFETCHCONTENT_SOURCE_DIR_IMGUI=/deps/ImGui \
    -DFETCHCONTENT_SOURCE_DIR_IMGUITEXTEDIT=/deps/ImGuiTextEdit \
    -DFETCHCONTENT_SOURCE_DIR_ICONFONTCPPHEADERS=/deps/IconFontCppHeaders \
    -DFETCHCONTENT_SOURCE_DIR_ZYDIS=/deps/zydis \
    -DFETCHCONTENT_SOURCE_DIR_FUNCHOOK=/deps/funchook \
    -DFETCHCONTENT_SOURCE_DIR_CORROSION=/deps/Corrosion \
    -DFETCHCONTENT_SOURCE_DIR_FMT=/deps/fmt -DFETCHCONTENT_SOURCE_DIR_GLFW=/deps/glfw \
    -DFETCHCONTENT_SOURCE_DIR_CONCURRENTQUEUE=/deps/concurrentqueue \
    && cmake --build /build --target UE4SS --parallel 4
COPY recipe/uehelpers-world.patch /recipe/uehelpers-world.patch
RUN patch /loader/Mods/shared/UEHelpers/UEHelpers.lua /recipe/uehelpers-world.patch \
    && cp /build/Game__Dev__Linux64/lib/libUE4SS.so /loader/libUE4SS.so

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ENV DEBIAN_FRONTEND=noninteractive PYTHONPATH=/opt/rhenium PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv libatomic1 libgl1 libegl1 libx11-6 libxrandr2 \
    libxinerama1 libxcursor1 libxi6 ca-certificates \
    && python3 -m venv /opt/python \
    && /opt/python/bin/pip install --no-cache-dir pydantic==2.13.4 tree-sitter==0.26.0 tree-sitter-lua==0.5.0 \
    && rm -rf /var/lib/apt/lists/* && useradd --uid 1001 --create-home evaluator
ENV PATH=/opt/python/bin:$PATH
COPY installation/ /server/
COPY --from=compiler /loader/ /server/ue4ss/
COPY --from=compiler /source/LICENSE /licenses/UE4SS-LICENSE
COPY code/ /opt/rhenium/
COPY recipe/ /opt/recipe/
RUN python3 /opt/recipe/seal.py && chown -R 1001:1001 /server
USER 1001:1001
WORKDIR /server
ENTRYPOINT ["python3", "/opt/recipe/server_worker.py"]
