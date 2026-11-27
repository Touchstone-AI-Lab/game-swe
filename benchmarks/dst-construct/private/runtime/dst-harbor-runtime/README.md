# DST Harbor verifier runtime

This is shared verifier infrastructure, not a benchmark task. It installs the
anonymous Don't Starve Together dedicated-server app (`343050`) with SteamCMD and
adds the repository's own DST evaluator. No Klei files are stored in Git, and the
resulting image is local and must never be pushed to a registry.

Both DST packs carry a byte-for-byte identical copy of this directory, and each
pack has its own runtime key:

| Pack | Build context | Runtime |
| --- | --- | --- |
| `dst/core` (repair tasks) | `benchmarks/dst/private/runtime/dst-harbor-runtime` | `dst/dst-dedicated-24700372` |
| `dst/construct` (construct tasks) | `benchmarks/dst-construct/private/runtime/dst-harbor-runtime` | `dst/dst-dedicated-24700372-construct` |

Build the frozen local images before running the DST tasks through the Hub:

```sh
rhenium auth login container
rhenium runtime prepare dst/dst-dedicated-24700372
rhenium runtime verify dst/dst-dedicated-24700372
rhenium runtime prepare dst/dst-dedicated-24700372-construct
rhenium runtime verify dst/dst-dedicated-24700372-construct
```

Each `prepare` builds `gcb-dst-dedicated-verifier:24700372` from its own pack's
copy of this directory and one verifier image per task from that pack's
`private/harbor/<task>/tests`. The two base images have the same content and
differ only in their runtime labels. Docker reuses the SteamCMD and server layers
from its build cache; only the layers from `COPY evaluator` on are rebuilt after
an evaluator change. The shared base tag moves to whichever pack was prepared
last. Each prepared runtime keeps referring to its own base image by image ID, and
`prepare` also tags that image `rhenium-dst:shared-base-<fingerprint>` so Docker's
image store keeps it after the shared tag moves. A Harbor trial needs only the
shared base tag; build it directly when the Hub is not used:

```sh
docker build --tag gcb-dst-dedicated-verifier:24700372 \
  benchmarks/dst/private/runtime/dst-harbor-runtime
```

Pins and their limits:

- The base image is the digest-pinned `ubuntu:24.04` declared in each pack's
  `runtimes.json`; the SteamCMD bootstrap archive is checked against a SHA-256 in
  the Dockerfile.
- `install-server.sh` requests the currently published public build and then
  requires build `24700372` in `appmanifest_343050.acf`. SteamCMD cannot request a
  historical build this way, so once Klei publishes a newer public build the image
  can no longer be rebuilt from scratch and the build fails closed. Keep the
  existing local image and its build cache; do not relax the pin to accept a newer
  download, and revalidate every reference first.
- `requirements.txt` pins the evaluator's Python dependencies to the versions in
  the repository `uv.lock`, including `lupa` for the construct pack's plain-Lua
  suites.
- `evaluator/` is a byte-for-byte copy of `src/rhenium/__init__.py`,
  `src/rhenium/core/` and `plugins/dst/src/rhenium_dst/`, written by each pack's
  `private/harbor/scripts/materialize.py`. The plugin serves both packs and picks
  the repair or construct evaluator by catalog. A plugin test fails when either
  copy drifts. The Hub binds each image to a fingerprint of its build context, so
  an evaluator change makes both prepared runtimes report unavailable until they
  are prepared again.
